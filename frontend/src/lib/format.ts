const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "Sep 30" from an ISO date (as-is) or a UTC datetime (shown in local time). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  if (iso.length > 10) {
    const d = new Date(iso)
    return `${MONTHS[d.getMonth()]} ${d.getDate()}`
  }
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return iso
  return `${MONTHS[m - 1]} ${d}`
}

/** "Sep 30, 14:05" in local time from a UTC ISO datetime. */
export function shortDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  if (iso.length <= 10) return shortDate(iso)
  const d = new Date(iso)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${MONTHS[d.getMonth()]} ${d.getDate()}, ${hh}:${mm}`
}

/** Wall-clock hours as "14 h" or "3.2 d". */
export function duration(hours: number | null | undefined): string {
  if (hours == null) return '—'
  if (hours < 48) return `${Math.round(hours)} h`
  return `${(hours / 24).toFixed(1)} d`
}

/** Slack to need-by: "+15d", "−2d". */
export function slack(days: number | null | undefined): string {
  if (days == null) return '—'
  if (days === 0) return '0d'
  return days > 0 ? `+${days}d` : `−${Math.abs(days)}d`
}

export function relativeAgo(iso: string | null | undefined): string {
  if (!iso) return ''
  const hours = (Date.now() - new Date(iso).getTime()) / 3_600_000
  if (hours < 1) return 'just now'
  return `${duration(hours)} ago`
}
