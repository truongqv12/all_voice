export function FlagIcon({ country, className = 'size-4 rounded-xs object-cover inline-block shrink-0' }: { country: 'vi' | 'en' | 'ja' | 'all'; className?: string }) {
  if (country === 'vi') {
    return (
      <svg className={className} viewBox="0 0 30 20" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Việt Nam">
        <rect width="30" height="20" fill="#DA251D" />
        <polygon
          points="15,4 16.18,7.63 20,7.63 16.91,9.88 18.09,13.51 15,11.26 11.91,13.51 13.09,9.88 10,7.63 13.82,7.63"
          fill="#FFFF00"
        />
      </svg>
    )
  }
  if (country === 'en') {
    return (
      <svg className={className} viewBox="0 0 30 20" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="English">
        <rect width="30" height="20" fill="#B22234" />
        <rect y="1.54" width="30" height="1.54" fill="#FFFFFF" />
        <rect y="4.62" width="30" height="1.54" fill="#FFFFFF" />
        <rect y="7.69" width="30" height="1.54" fill="#FFFFFF" />
        <rect y="10.77" width="30" height="1.54" fill="#FFFFFF" />
        <rect y="13.85" width="30" height="1.54" fill="#FFFFFF" />
        <rect y="16.92" width="30" height="1.54" fill="#FFFFFF" />
        <rect width="12" height="10.77" fill="#3C3B6E" />
        <circle cx="2.5" cy="2.5" r="0.8" fill="#FFFFFF" />
        <circle cx="6" cy="2.5" r="0.8" fill="#FFFFFF" />
        <circle cx="9.5" cy="2.5" r="0.8" fill="#FFFFFF" />
        <circle cx="4.25" cy="5.4" r="0.8" fill="#FFFFFF" />
        <circle cx="7.75" cy="5.4" r="0.8" fill="#FFFFFF" />
        <circle cx="2.5" cy="8.3" r="0.8" fill="#FFFFFF" />
        <circle cx="6" cy="8.3" r="0.8" fill="#FFFFFF" />
        <circle cx="9.5" cy="8.3" r="0.8" fill="#FFFFFF" />
      </svg>
    )
  }
  if (country === 'ja') {
    return (
      <svg className={className} viewBox="0 0 30 20" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="日本語">
        <rect width="30" height="20" fill="#FFFFFF" stroke="#CBD5E1" strokeWidth="0.8" />
        <circle cx="15" cy="10" r="6" fill="#BC002D" />
      </svg>
    )
  }
  return null
}
