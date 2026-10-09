import { useEffect, useState } from 'react'

/** Read colour tokens from CSS (they differ in light and dark mode) for the SVG charts. */
export function useCssColors<T extends string>(names: readonly T[]): Record<T, string> {
  const read = () => {
    const style = getComputedStyle(document.documentElement)
    return Object.fromEntries(names.map((n) => [n, style.getPropertyValue(`--${n}`).trim()])) as Record<T, string>
  }
  const [colors, setColors] = useState(read)
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setColors(read())
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return colors
}
