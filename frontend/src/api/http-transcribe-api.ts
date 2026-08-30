import type { TranscribeApi, TranscriptionResult, TranscriptSegment, TranscriptWord } from './transcribe-api';
import { ApiError } from './http-client';

const BASE_URL = import.meta.env.VITE_API_BASE || '/v1';

export function distributeWords(segments: any[], words: any[]): TranscriptSegment[] {
  const result: TranscriptSegment[] = segments.map(s => ({
    id: String(s.id),
    text: s.text?.trim() || '',
    start: s.start,
    end: s.end,
    words: []
  }));

  if (!words || !words.length) return result;

  for (const w of words) {
    const wordObj: TranscriptWord = {
      text: w.word,
      start: w.start,
      end: w.end
    };

    let matched = false;
    for (const seg of result) {
      if (w.start >= seg.start && w.start < seg.end) {
        seg.words.push(wordObj);
        matched = true;
        break;
      }
    }

    if (!matched) {
      // If it doesn't fit strictly inside any segment, find the closest one
      let closestSeg = result[0];
      let minDiff = Infinity;
      for (const seg of result) {
        const diff = Math.min(Math.abs(w.start - seg.start), Math.abs(w.start - seg.end));
        if (diff < minDiff) {
          minDiff = diff;
          closestSeg = seg;
        }
      }
      if (closestSeg) {
        closestSeg.words.push(wordObj);
      }
    }
  }

  return result;
}

export const httpTranscribeApi: TranscribeApi = {
  transcribe(file: File, onProgress: (stage: 'uploading' | 'transcribing', percent: number) => void): Promise<TranscriptionResult> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = `${BASE_URL}/audio/transcriptions`;

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress('uploading', Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const json = JSON.parse(xhr.responseText);
            const segments = distributeWords(json.segments || [], json.words || []);
            resolve({
              language: json.language || '',
              segments
            });
          } catch (err) {
            reject(new ApiError(xhr.status, 'parse_error', 'Invalid JSON response'));
          }
        } else {
          let code = 'unknown_error';
          let message = `HTTP error! status: ${xhr.status}`;
          try {
            const data = JSON.parse(xhr.responseText);
            if (data && data.error) {
              code = data.error.code || code;
              message = data.error.message || message;
            } else if (data && data.detail) {
              message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
              code = 'fastapi_error';
            }
          } catch (e) {
            if (xhr.responseText) message = xhr.responseText;
          }
          reject(new ApiError(xhr.status, code, message));
        }
      };

      xhr.onerror = () => {
        reject(new ApiError(0, 'network_error', 'Network error occurred'));
      };

      xhr.open('POST', url, true);
      
      const fd = new FormData();
      fd.append('file', file);
      fd.append('response_format', 'verbose_json');
      fd.append('timestamp_granularities[]', 'word');

      // Once uploaded, it's transcribing on the server (indeterminate)
      xhr.upload.onload = () => {
        onProgress('transcribing', 0); // indeterminate marker
      };

      xhr.send(fd);
    });
  }
};
