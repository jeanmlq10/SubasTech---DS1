import { expect, test } from "@playwright/test";

const apiURL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000/api";

test("public pages and API health are available", async ({ page, request }) => {
  const health = await request.get(`${apiURL}/health/`);
  expect(health.ok()).toBeTruthy();
  await expect(await health.json()).toEqual(expect.objectContaining({ status: "ok" }));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /encuentra tecnicos confiables/i })).toBeVisible();

  await page.goto("/login");
  await expect(page.getByText("Iniciar sesion")).toBeVisible();

  await page.goto("/demo");
  await expect(page.getByText(/subastech/i).first()).toBeVisible();
});
