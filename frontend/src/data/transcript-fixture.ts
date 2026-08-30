import type { TranscriptionResult } from '../api/transcribe-api'

export const transcriptFixture: TranscriptionResult = {
  language: 'vi',
  segments: [
    {
      id: 'segment-1', start: 0, end: 4.8, text: 'Xin chào, đây là bản chép lời mẫu cho All Voice.',
      words: [
        { text: 'Xin', start: 0, end: 0.34 }, { text: 'chào,', start: 0.36, end: 0.75 },
        { text: 'đây', start: 0.98, end: 1.19 }, { text: 'là', start: 1.21, end: 1.35 },
        { text: 'bản', start: 1.38, end: 1.6 }, { text: 'chép', start: 1.62, end: 1.9 },
        { text: 'lời', start: 1.92, end: 2.12 }, { text: 'mẫu', start: 2.14, end: 2.39 },
        { text: 'cho', start: 2.42, end: 2.61 }, { text: 'All', start: 2.63, end: 2.91 },
        { text: 'Voice.', start: 2.93, end: 3.35 },
      ],
    },
    {
      id: 'segment-2', start: 5.15, end: 10.25, text: 'Bạn có thể kiểm tra từng câu, rồi xuất phụ đề SRT, VTT hoặc văn bản thuần.',
      words: [
        { text: 'Bạn', start: 5.15, end: 5.38 }, { text: 'có', start: 5.4, end: 5.54 },
        { text: 'thể', start: 5.56, end: 5.77 }, { text: 'kiểm', start: 5.79, end: 6.08 },
        { text: 'tra', start: 6.1, end: 6.31 }, { text: 'từng', start: 6.34, end: 6.58 },
        { text: 'câu,', start: 6.61, end: 6.87 }, { text: 'rồi', start: 7.14, end: 7.33 },
        { text: 'xuất', start: 7.35, end: 7.59 }, { text: 'phụ', start: 7.61, end: 7.82 },
        { text: 'đề', start: 7.84, end: 8.05 }, { text: 'SRT,', start: 8.09, end: 8.39 },
        { text: 'VTT', start: 8.42, end: 8.69 }, { text: 'hoặc', start: 8.72, end: 8.98 },
        { text: 'văn', start: 9.01, end: 9.23 }, { text: 'bản', start: 9.25, end: 9.47 },
        { text: 'thuần.', start: 9.5, end: 9.96 },
      ],
    },
  ],
}
