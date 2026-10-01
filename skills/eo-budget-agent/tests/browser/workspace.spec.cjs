const { test, expect } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const sample = () =>
  JSON.parse(
    fs.readFileSync(path.join(root, "data/sample-project.json"), "utf8"),
  );

async function importProject(page, project) {
  await page.locator("#export-menu").click();
  await page.locator("#import-file").setInputFiles({
    name: "project.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ project })),
  });
  await expect(page.locator("#workspace-dialog")).not.toBeVisible();
  await expect(page.locator("#sync-state")).toContainText("tersinkron");
}

test.beforeEach(async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  await expect(page.locator(".metric-card")).toHaveCount(4);
  await expect(page.locator("#sync-state")).toContainText("tersinkron");
});

test("overview has six real agents and honest estimate disclosure", async ({
  page,
}) => {
  await expect(page.locator(".agent-card")).toHaveCount(6);
  await expect(page.locator(".notice-strip")).toContainText(
    "tarif template adalah ilustrasi",
  );
  await expect(page.locator(".budget-progress-fill")).toHaveCSS(
    "width",
    /[1-9]/,
  );
  await page.locator("#run-agents").click();
  await expect(page.locator("#sync-state")).toContainText("tersinkron");
  await expect(page.locator(".toast")).toContainText("6 agent selesai");
});

test("RAB edits recalculate without losing focus and filters work", async ({
  page,
}) => {
  await page.locator("#tab-rab").click();
  await page.locator("#price-venue").fill("25000000");
  await expect(
    page.locator(".rab-table tbody tr").first().locator(".money-cell"),
  ).toHaveText("25.000.000");
  await expect(page.locator("#price-venue")).toBeFocused();
  await page.locator("#rab-search").fill("LED");
  await expect(page.locator(".rab-table tbody tr")).toHaveCount(1);
  await expect(page.locator("#rab-search")).toHaveValue("LED");
  await page.locator("#rab-search").fill("");
  await page.locator("#rab-category").selectOption("safety");
  await expect(page.locator(".rab-table tbody tr")).toHaveCount(2);
});

test("invalid finance input preserves the last snapshot and can recover", async ({
  page,
}) => {
  await page.locator("#tab-pricing").click();
  await page.locator("#f-targetMarginPercent").fill("100");
  await expect(page.locator("#validation-banner")).toBeVisible();
  await expect(page.locator("#validation-banner")).toContainText(
    "snapshot terakhir",
  );
  await page.locator("#f-targetMarginPercent").fill("30");
  await expect(page.locator("#validation-banner")).not.toBeVisible();
  await expect(
    page.locator(".scenario-card.recommended .scenario-meta"),
  ).toContainText("30");
});

test("blank required numeric field is not silently treated as its previous value", async ({
  page,
}) => {
  await page.locator("#tab-pricing").click();
  await page.locator("#f-clientBudget").fill("");
  await expect(page.locator("#validation-banner")).toBeVisible();
  await page.locator("#f-clientBudget").fill("300000000");
  await expect(page.locator("#validation-banner")).not.toBeVisible();
});

test("tax changes invalidate review and affect invoice, not HPP", async ({
  page,
}) => {
  await page.locator("#tab-pricing").click();
  const before = await page
    .locator(".sale-card .cost-line.total")
    .first()
    .textContent();
  await page.locator("#f-taxStatus").selectOption("pkp");
  await expect(page.locator("#sync-state")).toContainText("tersinkron");
  await page.locator("#f-taxVerified").check();
  await expect(page.locator("#sync-state")).toContainText("tersinkron");
  await page.locator("#f-vatPercent").fill("11");
  await expect(page.locator("#f-taxVerified")).not.toBeChecked();
  await expect(page.locator(".sale-card")).toContainText("PPN efektif 11%");
  await expect(page.locator(".sale-card .cost-line.total").first()).toHaveText(
    before,
  );
  await page.locator("#f-taxStatus").selectOption("non_pkp");
  await expect(page.locator("#f-vatPercent")).toHaveValue("0");
});

test("brief changes scale only declared variable items", async ({ page }) => {
  await page.locator("[data-edit-brief]").click();
  await page.locator('#dialog-form [name="attendees"]').fill("300");
  await page.locator('#dialog-form [name="eventDays"]').fill("2");
  await page.locator("#dialog-submit").click();
  await expect(page.locator("#workspace-dialog")).not.toBeVisible();
  await expect(page.locator("#project-strip")).toContainText("300 peserta");
  await page.locator("#tab-rab").click();
  await expect(page.locator("#qty-catering")).toHaveValue("300");
  await expect(page.locator("#duration-catering")).toHaveValue("2");
  await expect(page.locator("#duration-crew")).toHaveValue("3");
  await expect(page.locator("#qty-stage")).toHaveValue("1");
});

test("new item has validated fields and quote cannot be asserted without evidence", async ({
  page,
}) => {
  await page.locator("#tab-rab").click();
  await page.locator("[data-add-item]").click();
  await page
    .locator('#dialog-form [name="name"]')
    .fill("Extra registration signage");
  await page.locator('#dialog-form [name="unitPrice"]').fill("750000");
  await page.locator('#dialog-form [name="confidence"]').selectOption("quote");
  await page.locator("#dialog-submit").click();
  await expect(page.locator("#dialog-error")).toContainText("vendor");
  await page
    .locator('#dialog-form [name="confidence"]')
    .selectOption("estimate");
  await page.locator("#dialog-submit").click();
  await expect(page.locator("#workspace-dialog")).not.toBeVisible();
  await expect(page.locator(".rab-table")).toContainText(
    "Extra registration signage",
  );
});

test("CSV export is a usable download and JSON import normalizes optional fields", async ({
  page,
}) => {
  await page.locator("#export-menu").click();
  const pending = page.waitForEvent("download");
  await page.locator('[data-export="csv"]').click();
  const downloaded = await pending;
  expect(downloaded.suggestedFilename()).toBe("rab-internal.csv");
  const file = fs.readFileSync(await downloaded.path(), "utf8");
  expect(file).toContain("HPP proyek full cost");
  const project = sample();
  project.event.name = "Imported & validated workspace";
  delete project.observations;
  delete project.audit;
  await importProject(page, project);
  await expect(page.locator("#project-strip")).toContainText(
    project.event.name,
  );
  await page.locator("#tab-learning").click();
  await expect(page.locator(".learning-stats")).toContainText(
    "Observasi tercatat",
  );
  await page.reload();
  await expect(page.locator("#project-strip")).toContainText(
    project.event.name,
  );
});

test("learning approval updates a rate, resets quote, and creates a local audit", async ({
  page,
}) => {
  const project = sample(),
    row = project.items[0];
  row.confidence = "quote";
  row.vendor = "Test vendor";
  row.reference = "TEST-QUOTE";
  const { today } = await (await page.request.get("/api/bootstrap")).json();
  row.verifiedAt = today;
  row.validUntil = project.event.date > today ? project.event.date : today;
  project.observations = [21000000, 22000000, 23000000].map((rate, index) => ({
    itemId: row.id,
    eventId: `completed-${index}`,
    eventType: project.event.type,
    city: project.event.city,
    specification: row.name,
    unit: row.unit,
    unitPrice: rate,
    recordedAt: today,
  }));
  await importProject(page, project);
  await page.locator("#tab-learning").click();
  await expect(page.locator('[data-apply-item="venue"]')).toBeEnabled();
  await page.locator('[data-apply-item="venue"]').click();
  await expect(page.locator(".audit-item")).toContainText("20.500.000");
  await page.locator("#tab-rab").click();
  await expect(page.locator("#price-venue")).toHaveValue("20500000");
  await expect(page.locator(".rab-table tbody tr").first()).toContainText(
    "Estimasi",
  );
});

test("realizations for the same project are not counted as separate events", async ({
  page,
}) => {
  await page.locator("#tab-learning").click();
  await page.locator("#actual-venue").fill("22000000");
  await expect(page.locator("#archive-actuals")).toBeEnabled();
  await page.locator("#archive-actuals").click();
  await expect(
    page.locator(".learning-stats .learning-stat").first().locator("strong"),
  ).toHaveText("1");
  await page.locator("#archive-actuals").click();
  await expect(
    page.locator(".learning-stats .learning-stat").first().locator("strong"),
  ).toHaveText("1");
  await expect(page.locator('[data-apply-item="venue"]')).toBeDisabled();
});

test("client draft omits internal cost values and labels itself as unapproved", async ({
  page,
}) => {
  await page.locator("#tab-pricing").click();
  const pending = page.waitForEvent("download");
  await page.locator('[data-export="proposal"]').click();
  const file = fs.readFileSync(await (await pending).path(), "utf8");
  expect(file).toContain("DRAFT — belum disetujui");
  expect(file).not.toContain("Tarif satuan");
  expect(file).not.toContain("Laba proyeksi");
});

test("mobile layout remains within viewport and navigation works", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".metric-card")).toHaveCount(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.locator("#mobile-menu").click();
  await expect(page.locator("#sidebar")).toHaveClass(/open/);
  await page.locator('#sidebar [data-tab="rab"]').click();
  await expect(page.locator(".rab-table")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.locator("#tab-pricing").click();
  await expect(page.locator(".pricing-scenarios")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("no uncaught script errors or CSP violations across workspace views", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      /Content Security Policy|Refused to/.test(message.text())
    )
      errors.push(message.text());
  });
  for (const tab of ["rab", "pricing", "agents", "learning", "overview"]) {
    await page.locator(`#tab-${tab}`).click();
    await expect(page.locator("#content")).not.toBeEmpty();
  }
  expect(errors).toEqual([]);
});

test("invalid browser backup recovers without an uncaught startup error", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.evaluate(() =>
    localStorage.setItem(
      "panggung.eo.project.v1",
      JSON.stringify({ schemaVersion: 1 }),
    ),
  );
  await page.reload();
  await expect(page.locator(".metric-card")).toHaveCount(4);
  await expect(page.locator("#toasts")).toContainText(
    "Backup browser tidak valid",
  );
  expect(errors).toEqual([]);
});

test("untrusted project text is displayed as text, not executable markup", async ({
  page,
}) => {
  const project = sample();
  project.event.name = '<img src=x onerror="window.EO_INJECTED=true">';
  await importProject(page, project);
  await expect(page.locator("#project-strip h2")).toHaveText(
    project.event.name,
  );
  await expect(page.locator("#project-strip img")).toHaveCount(0);
  expect(await page.evaluate(() => window.EO_INJECTED)).toBeUndefined();
});
