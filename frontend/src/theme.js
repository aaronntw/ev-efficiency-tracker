const key = 'ev-efficiency-theme'

export function initialTheme() {
  try {
    const saved = localStorage.getItem(key)
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* Storage can be disabled; keep the switch usable. */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function saveTheme(theme) {
  try { localStorage.setItem(key, theme) } catch { /* Use in-memory state. */ }
}

document.documentElement.dataset.theme = initialTheme()
