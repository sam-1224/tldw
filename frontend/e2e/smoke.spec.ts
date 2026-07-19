import { test, expect, Page } from "@playwright/test";

const CONFIG = {
  free_tier_available: true,
  default_provider: "gemini",
  free_chain: ["gemini", "groq"],
  summary_languages: ["English", "Español"],
  providers: [
    {
      id: "gemini", label: "Google Gemini", default_model: "gemini-flash-latest",
      models: ["gemini-flash-latest"], key_optional: false, needs_base_url: false,
    },
    {
      id: "groq", label: "Groq", default_model: "llama-3.3-70b-versatile",
      models: ["llama-3.3-70b-versatile"], key_optional: false, needs_base_url: false,
    },
    {
      id: "custom", label: "Custom / local", default_model: "",
      models: [], key_optional: true, needs_base_url: true,
    },
  ],
};

const RESULT = {
  video_id: "dQw4w9WgXcQ",
  duration_seconds: 3600,
  transcript_source: "captions",
  transcript_language: "hi",
  title: "E2E test video",
  author: "tester",
  thumbnail: "",
  segments: Array.from({ length: 450 }, (_, i) => ({
    text: `segment ${i}`, start: i * 8, duration: 8,
  })),
  summary: {
    tldr: "E2E tldr.",
    breakdown: ["Breakdown para."],
    key_points: [
      { timestamp: "10:00", point: "First", detail: "d1" },
      { timestamp: "40:00", point: "Second", detail: "d2" },
    ],
    takeaways: ["Takeaway one"],
    worth_watching: { score: 8, reason: "dense" },
    topics: ["alpha", "beta"],
    truncated: false,
  },
};

async function mockApi(page: Page) {
  await page.route("**/api/config", (route) =>
    route.fulfill({ json: CONFIG }),
  );
  await page.route("**/api/summarize", (route) =>
    route.fulfill({ json: RESULT }),
  );
}

async function summarize(page: Page) {
  await page.getByPlaceholder(/youtube\.com\/watch/).fill("https://youtu.be/dQw4w9WgXcQ");
  await page.getByRole("button", { name: "Summarize" }).click();
}

test("app boots with free tier detected", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /watch less/i })).toBeVisible();
  await expect(page.getByText("— free tier, no key needed")).toBeVisible();
});

test("mocked summarize renders all bento cards", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await summarize(page);

  for (const area of ["tldr", "moments", "breakdown", "takeaways", "worth", "transcript"]) {
    await expect(page.locator(`.area-${area}`)).toBeVisible();
  }
  await expect(page.locator(".bento-card.tldr")).toContainText("E2E tldr.");
  await expect(page.locator(".vid .badge")).toContainText("HI → EN");
  // entrance animation completes: card fully opaque
  await expect
    .poll(async () =>
      page.locator(".bento-card.tldr").evaluate((el) => getComputedStyle(el).opacity),
    )
    .toBe("1");
  // timeline ticks land with working deep links
  const tick = page.locator(".timeline .tick").first();
  await expect(tick).toHaveAttribute("href", /t=600s/);
  // landing collapsed
  await expect(page.locator(".hero.compact")).toBeVisible();
});

test("settings persist across reload", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Open settings" }).click();
  await page.getByRole("tab", { name: "Your API key" }).click();
  await page.locator("#provider").selectOption("groq");
  await page.locator("#llmKey").fill("test-key-123");
  await page.getByRole("button", { name: "Save to this browser" }).click();
  await page.reload();
  await page.getByRole("button", { name: "Open settings" }).click();
  await expect(page.locator("#provider")).toHaveValue("groq");
  await expect(page.locator("#llmKey")).toHaveValue("test-key-123");
});

test("reduced motion renders instantly without entrance animation", async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: "reduce" });
  const page = await context.newPage();
  await mockApi(page);
  await page.goto("/");
  await summarize(page);
  await expect(page.locator(".bento-card.tldr")).toBeVisible();
  const opacity = await page
    .locator(".bento-card.tldr")
    .evaluate((el) => getComputedStyle(el).opacity);
  expect(opacity).toBe("1");
  // hero highlighter swipe is disabled: mark fully painted immediately
  await context.close();
});

test("mobile 390x844 has no horizontal scroll", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await mockApi(page);
  await page.goto("/");
  await summarize(page);
  await expect(page.locator(".bento-card.tldr")).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await context.close();
});
