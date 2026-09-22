import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  let record = {
    id: 1, charged_at: '2026-09-20T10:00:00Z', odometer_km: 2000,
    soc_before: 20, soc_after: 80, kwh_charged: 36, amount_paid: 30,
    connector_type: 'DC', provider: 'Test provider', location: 'Old location', notes: '',
    efficiency_km_per_kwh: 6, distance_km: 120, estimated_energy_used_kwh: 20,
    efficiency_percent: 90, charging_cost_per_kwh: 0.83, charging_cost_per_km: 0.25,
  }
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/charges/1' && route.request().method() === 'PUT') {
      record = { ...record, ...route.request().postDataJSON() }
      return route.fulfill({ json: record })
    }
    const data = {
      '/api/charges': [record],
      '/api/settings': { vehicle_name: 'Test EV', usable_battery_kwh: 60, maximum_range_km: 400, currency: 'RM' },
      '/api/providers': [{ id: 1, name: 'Test provider' }],
      '/api/version': { version: '1.4.3', build_sha: 'test', database: 'sqlite', timezone: 'UTC' },
    }
    return route.fulfill({ json: data[path] ?? {} })
  })
})

test('editing from Records returns to Records with the saved value', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Records', exact: true }).click()
  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  await page.getByLabel('Location', { exact: true }).fill('Updated location')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('heading', { name: 'Charging records' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'Updated location' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Dashboard period' })).toHaveCount(0)
})

test('edits started on Dashboard return to Dashboard', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard period' })).toBeVisible()
})

test('failed saves retain the edit and show the error', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Records', exact: true }).click()
  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  await page.route('**/api/charges/1', route => route.fulfill({ status: 500, body: 'Save failed' }))
  await page.getByLabel('Location', { exact: true }).fill('Unsaved location')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Save failed', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Location', { exact: true })).toHaveValue('Unsaved location')
})

test('theme follows the system initially and persists an explicit keyboard choice', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/')
  const toggle = page.getByRole('switch', { name: 'Dark mode' })
  await expect(toggle).toHaveAttribute('aria-checked', 'true')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await toggle.focus()
  await expect(toggle).toBeFocused()
  expect(await toggle.evaluate(el => getComputedStyle(el).outlineStyle)).toBe('solid')
  await toggle.press('Space')
  await expect(toggle).toHaveAttribute('aria-checked', 'false')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(toggle).toHaveAttribute('aria-checked', 'false')
  await toggle.click()
  await page.emulateMedia({ colorScheme: 'light' })
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

test('theme switches without losing form input or navigation', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.getByRole('button', { name: '+ Charging', exact: true }).click()
  await page.getByLabel('Location', { exact: true }).fill('Unsaved charging location')
  await page.getByRole('switch', { name: 'Dark mode' }).click()
  await expect(page.getByLabel('Location', { exact: true })).toHaveValue('Unsaved charging location')
  await expect(page.getByRole('heading', { name: 'Record charging session' })).toBeVisible()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await page.getByLabel('Vehicle name').fill('Unsaved vehicle')
  await page.getByRole('switch', { name: 'Dark mode' }).click()
  await expect(page.getByLabel('Vehicle name')).toHaveValue('Unsaved vehicle')
})

test('theme remains usable when browser storage is blocked', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage disabled') } })
  })
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')
  await page.getByRole('switch', { name: 'Dark mode' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})
