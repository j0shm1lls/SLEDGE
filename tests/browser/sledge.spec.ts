import { expect, test } from '@playwright/test'

for (const state of ['Steam native', 'Downloading', 'Paused', 'Overheat', 'Fallback']) {
  test(`preview can simulate ${state}`, async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()) })
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.getByRole('heading', { name: /Make custom lighting feel native/i })).toBeVisible()
    await page.getByRole('button', { name: new RegExp(`^${state}`) }).click()
    await expect(page.getByRole('button', { name: new RegExp(`^${state}`) })).toHaveClass(/active/)
    await expect(page.getByText('Steam owns the bar.')).toBeVisible()
    expect(errors).toEqual([])
  })
}

test('starts with 24 physical LEDs and demo can be restarted', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.locator('.led-strip')).toHaveAttribute('data-led-count', '24')
  await expect(page.locator('.led')).toHaveCount(24)
  await expect(page.locator('.hero-hammer')).toBeVisible()
  await expect(page.locator('.hammer-led')).toHaveCount(24)
  await expect(page.getByRole('link', { name: 'SLEDGE', exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^Downloading/ }).click()
  await expect(page.getByRole('button', { name: /^Restart demo/ })).not.toHaveClass(/active/)
  await page.getByRole('button', { name: /^Restart demo/ }).click()
  await expect(page.getByRole('button', { name: /^Restart demo/ })).toHaveClass(/active/)
})

test('download, mapping, direction, pause, effect, and thermal controls are interactive', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: /^Downloading/ }).click()
  await page.getByRole('radio', { name: 'nearest' }).click()
  await expect(page.getByRole('radio', { name: 'nearest' })).toHaveAttribute('data-state', 'on')
  await expect(page.getByText(/17 → 24 mapping/)).toBeVisible()

  await expect(page.getByText('Choose the direction that makes download progress fill the way you expect.')).toBeVisible()
  await page.getByRole('radio', { name: 'Reverse' }).click()
  await expect(page.getByRole('radio', { name: 'Reverse' })).toHaveAttribute('data-state', 'on')
  await page.getByRole('radio', { name: 'Forward' }).click()
  await expect(page.getByRole('radio', { name: 'Forward' })).toHaveAttribute('data-state', 'on')

  await page.getByRole('checkbox', { name: 'Pause download' }).check()
  await expect(page.getByRole('button', { name: /^Paused/ })).toHaveClass(/active/)

  await page.getByRole('radio', { name: 'rainbow' }).click()
  await page.getByRole('button', { name: /^Fallback/ }).click()
  await expect(page.getByRole('radio', { name: 'rainbow' })).toHaveAttribute('data-state', 'on')
  await expect(page.getByLabel('Trip temperature')).toHaveValue('85')
  await expect(page.getByLabel('Clear temperature')).toHaveValue('80')
})

test('mobile touch targets stay at least 52px tall', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile-only geometry check')
  await page.goto('/', { waitUntil: 'networkidle' })
  const box = await page.getByRole('button', { name: /^Steam native/ }).boundingBox()
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(52)
  await expect(page.locator('main')).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBe(false)
})
