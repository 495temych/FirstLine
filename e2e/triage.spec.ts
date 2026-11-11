import { expect, test, type Page } from "@playwright/test";

// The web fonts are slow to load, and a test has no need of them.
test.beforeEach(async ({ page }) => {
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) =>
    route.abort(),
  );
});

/** Opens a group, then one of its views, through their links. */
async function open(page: Page, ...names: string[]) {
  for (const name of names) {
    await page.getByRole("link", { name, exact: true }).click();
  }
}

async function triage(page: Page, ticket: string, requester = "s.keller") {
  await page.goto("/");
  await open(page, "Assistant");
  await page.getByLabel("Who is asking").selectOption(requester);
  await page.getByLabel("Describe the issue").fill(ticket);
  await page.getByRole("button", { name: "Triage this ticket" }).click();
}

test("a fix runs only after confirmation", async ({ page }) => {
  await triage(page, "fix my VPN");
  await expect(page.getByText("Auto-fix")).toBeVisible();
  await expect(page.getByText("Fix ran (simulated)")).toBeHidden();
  await page.getByRole("button", { name: "Run fix" }).click();
  await expect(page.getByText("Fix ran (simulated)")).toBeVisible();
});

test("a declined fix gives a pre-filled ticket", async ({ page }) => {
  await triage(page, "fix my VPN");
  await page.getByRole("button", { name: "Decline fix" }).click();
  await expect(page.getByText(/no new model call/)).toBeVisible();
  await page
    .getByRole("button", { name: "Create ticket", exact: true })
    .click();
  await expect(page.getByText(/Ticket INC\d+ created/)).toBeVisible();
});

test("the same lockout goes to security only for a repeat lockout", async ({
  page,
}) => {
  await triage(page, "I'm locked out of my account", "s.keller");
  await expect(page.getByText("Changed by a rule: SEC-04.")).toBeVisible();
  await expect(page.getByText("SEC-INCIDENT", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run fix" })).toBeHidden();

  await triage(page, "I'm locked out of my account", "m.huber");
  await expect(
    page.getByText("Changed by a rule: Sensitive fix."),
  ).toBeVisible();
  await expect(page.getByText("DESK-SUPPORT", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run fix" })).toBeHidden();
});

test("an escalation waits for confirmation", async ({ page }) => {
  await triage(page, "lockout again");
  await expect(page.getByText("SEC-INCIDENT", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Don't create ticket" }).click();
  await expect(page.getByText("No ticket created.")).toBeVisible();
});

test("failed self-serve steps go to a ticket", async ({ page }) => {
  await triage(page, "steps for my dock");
  await expect(page.getByText("Self-serve")).toBeVisible();
  await page.getByRole("button", { name: /It didn't/ }).click();
  await page
    .getByRole("button", { name: "Create ticket", exact: true })
    .click();
  await expect(page.getByText(/Ticket INC\d+ created/)).toBeVisible();
});

test("self-serve steps can resolve a ticket", async ({ page }) => {
  await triage(page, "steps for my dock");
  await page.getByRole("button", { name: "This resolved it" }).click();
  await expect(page.getByText("Marked as resolved.")).toBeVisible();
});

test("an out-of-scope ticket takes no action", async ({ page }) => {
  await triage(page, "the weather");
  await expect(page.getByText(/no action was taken/)).toBeVisible();
});

test("a gate survives a reload", async ({ page }) => {
  await triage(page, "fix my VPN");
  await expect(page.getByRole("button", { name: "Run fix" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Run fix" }).click();
  await expect(page.getByText("Fix ran (simulated)")).toBeVisible();
});

test("each group shows its views, and a saved evaluation", async ({ page }) => {
  await page.goto("/");
  await open(page, "Is it worth it?");
  await expect(page.getByText(/nothing to project/)).toBeVisible();
  await open(page, "Models");
  await expect(
    page.getByText(/No model has a development run yet/),
  ).toBeVisible();
  await open(page, "How it works", "Evaluations");
  await expect(page.getByText("rules set (tiny)")).toBeVisible();
  await expect(page.getByLabel("Open an evaluation")).toBeVisible();
});

test("a shared link opens its view, and back returns", async ({ page }) => {
  await page.goto("/?view=retrieval");
  await expect(
    page.getByRole("link", { name: "Retrieval", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await open(page, "Tickets");
  await expect(page).toHaveURL(/view=tickets/);
  await page.goBack();
  await expect(page).toHaveURL(/view=retrieval/);
});

test("the tickets tab can be filtered", async ({ page }) => {
  await page.goto("/");
  await open(page, "How it works", "Tickets");
  await expect(page.getByText("206 of 206 tickets")).toBeVisible();
  await page.getByRole("button", { name: "records" }).click();
  await expect(page.getByText("5 of 206 tickets")).toBeVisible();
  await page.getByRole("button", { name: "records" }).click();
  await page.getByLabel("Family").selectOption("VPN access");
  await expect(page.getByText("12 of 206 tickets")).toBeVisible();
  await page.getByLabel("Cause").selectOption("Stale VPN profile");
  await expect(page.getByText("1 of 206 tickets")).toBeVisible();
});

test("the page fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await triage(page, "fix my VPN");
  await expect(page.getByRole("button", { name: "Run fix" })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the queue works a batch and waits for a technician", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/The board is empty/)).toBeVisible();
  await page
    .getByRole("button", { name: /Load 8 tickets from the service desk/ })
    .click();
  const waiting = page.locator(".column-review .card");
  await expect(waiting).toHaveCount(8);
  await waiting.first().click();
  await expect(page.getByText(/Tracing is off/)).toBeVisible();
  await page.getByRole("button", { name: /^Approve and/ }).click();
  await expect(waiting).toHaveCount(7);
  await expect(page.locator(".column-closed .chip-approved")).toHaveCount(1);
  await expect(
    page.getByRole("region", { name: "How the batch went" }),
  ).toContainText("1 of 1");
});

test("the queue fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page.getByText(/waiting at the desk/)).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("how it works follows a ticket along its route", async ({ page }) => {
  await page.goto("/");
  await open(page, "How it works");
  await expect(page.getByText(/correct first pass/).first()).toBeVisible();
  await page.getByLabel("Escalate").check();
  await page
    .getByRole("button", { name: /Approve the ticket/ })
    .first()
    .click();
  await expect(page.getByText("A person decides here.")).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("how it works fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await open(page, "How it works");
  await expect(page.getByText(/correct first pass/).first()).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("retrieval shows its scores and runs a search", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await open(page, "How it works", "Retrieval");
  await expect(
    page.getByText(/correctly finds none/, { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("A request, as someone would write it")
    .fill("My VPN drops");
  await page
    .getByRole("button", { name: "Search the knowledge base, free" })
    .click();
  await expect(page.getByText("The knowledge base is empty.")).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the model benchmark fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await open(page, "Is it worth it?", "Models");
  await expect(
    page.getByText(/No model has a development run yet/),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the business case fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await open(page, "Is it worth it?");
  await expect(page.getByText(/nothing to project/)).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the harness draws one call and fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await open(page, "How it works", "Harness");
  await expect(
    page.getByRole("complementary", { name: "The loop" }),
  ).toContainText("No loop yet.");
  await expect(
    page.getByText("record_decision, which it must call"),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
