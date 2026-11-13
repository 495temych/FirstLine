import { expect, test, type Page } from "@playwright/test";

// The web fonts are slow to load, and a test has no need of them.
test.beforeEach(async ({ page }) => {
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) =>
    route.abort(),
  );
});

/** Opens a view through the sidebar, from the menu at phone width. */
async function open(page: Page, name: string) {
  const link = page.getByRole("link", { name, exact: true });
  if (!(await link.isVisible())) {
    await page.getByRole("button", { name: "Menu" }).click();
  }
  await link.click();
}

async function triage(page: Page, ticket: string, requester = "s.keller") {
  await page.goto("/");
  await open(page, "Assistant");
  await page.getByLabel("Who is asking").selectOption(requester);
  await page.getByLabel("Describe the issue").fill(ticket);
  await page.getByRole("button", { name: "Triage this ticket" }).click();
}

/** The path the agent chose, as its reply names it. */
const chosen = (page: Page) =>
  page.getByRole("region", { name: "FirstLine's reply" }).locator(".path-name");

/** The card where a person decides. */
const gate = (page: Page) =>
  page.getByRole("region", { name: "Waiting for you" });

const steps = (page: Page) =>
  page.getByRole("list", { name: "The agent's steps" }).getByRole("listitem");

test("a fix runs only after confirmation", async ({ page }) => {
  await triage(page, "fix my VPN");
  await expect(chosen(page)).toHaveText("Auto-fix");
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
  await expect(
    gate(page).getByText("SEC-INCIDENT", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Run fix" })).toBeHidden();

  await triage(page, "I'm locked out of my account", "m.huber");
  await expect(
    page.getByText("Changed by a rule: Sensitive fix."),
  ).toBeVisible();
  await expect(
    gate(page).getByText("DESK-SUPPORT", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Run fix" })).toBeHidden();
});

test("an escalation waits for confirmation", async ({ page }) => {
  await triage(page, "lockout again");
  await expect(
    gate(page).getByText("SEC-INCIDENT", { exact: true }),
  ).toBeVisible();
  const handover = gate(page).getByRole("region", {
    name: "Handover to SEC-INCIDENT",
  });
  await expect(
    handover.getByText("Find the device that sends the old password."),
  ).toBeVisible();
  await expect(handover.getByText(/Immediate/)).toBeVisible();
  await page.getByRole("button", { name: "Don't create ticket" }).click();
  await expect(page.getByText("No ticket created.")).toBeVisible();
});

test("failed self-serve steps go to a ticket", async ({ page }) => {
  await triage(page, "steps for my dock");
  await expect(chosen(page)).toHaveText("Self-serve");
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

test("the reply shows each step of the loop, then waits", async ({ page }) => {
  await triage(page, "I'm locked out of my account", "s.keller");
  const reply = page.getByRole("region", { name: "FirstLine's reply" });
  await expect(reply.locator(".sender")).toContainText("Working");
  const gate = page.getByRole("region", { name: "Waiting for you" });
  await expect(gate).toBeVisible();
  await expect(steps(page).locator(".check-label")).toHaveText([
    "Search the knowledge base",
    "Look up the requester",
    "Run the check account-lockout-source-check",
    "Decide",
    "Apply the rules: SEC-04 changed it",
  ]);
  await expect(
    gate.getByRole("button", { name: "Create ticket", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(steps(page)).toHaveCount(5);
  await expect(gate).toBeVisible();
});

test("a step opens from the keyboard to show what it read", async ({
  page,
}) => {
  await triage(page, "I'm locked out of my account", "s.keller");
  const lookup = steps(page).filter({ hasText: "Look up the requester" });
  await expect(lookup.getByText(/2 lockouts in 24 hours/)).toBeVisible();
  await expect(lookup.getByText("lookup_requester")).toBeHidden();
  await lookup.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(lookup.getByText("lookup_requester")).toBeVisible();
});

test("a real example ticket comes with its requester", async ({ page }) => {
  await page.goto("/");
  await open(page, "Assistant");
  const examples = page.getByRole("list", { name: "Real tickets" });
  await examples.getByRole("button").first().click();
  const text = await page.getByLabel("Describe the issue").inputValue();
  expect(text.length).toBeGreaterThan(0);
  const who = await page.getByLabel("Who is asking").inputValue();
  await page.getByRole("button", { name: "Triage this ticket" }).click();
  await expect(page.locator(".from-person .sender").first()).toContainText(who);
  await expect(steps(page).first()).toBeVisible();
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
  await open(page, "Money");
  await expect(page.getByText(/nothing to project/)).toBeVisible();
  await open(page, "Models");
  await expect(
    page.getByText(/No model has a development run yet/),
  ).toBeVisible();
  await open(page, "Evaluations");
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
  await open(page, "Tickets");
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
  await open(page, "Workflow");
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
  await open(page, "Workflow");
  await expect(page.getByText(/correct first pass/).first()).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("retrieval shows its scores and runs a search", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await open(page, "Retrieval");
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
  await open(page, "Models");
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
  await open(page, "Money");
  await expect(page.getByText(/nothing to project/)).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the harness draws one call and fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await open(page, "Harness");
  await expect(
    page.getByRole("complementary", { name: "The loop" }),
  ).toContainText("No loop in the default design.");
  await expect(
    page.getByText("record_decision, which it must call"),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
