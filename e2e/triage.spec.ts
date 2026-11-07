import { expect, test, type Page } from "@playwright/test";

async function triage(page: Page, ticket: string) {
  await page.goto("/");
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

test("the scoreboard shows a saved evaluation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Scoreboard" }).click();
  await expect(page.getByText("rules set (tiny)")).toBeVisible();
  await expect(page.getByLabel("Open an evaluation")).toBeVisible();
  await expect(page.getByText("unseen, development")).toBeVisible();
  await expect(page.getByLabel("Open a retrieval score")).toBeVisible();
});

test("the tickets tab can be filtered", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Tickets" }).click();
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
