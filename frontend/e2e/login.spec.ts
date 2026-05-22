import { expect, test, type Page } from "@playwright/test";

const password = "Subastech123!";

async function loginAs(page: Page, username: string) {
  await page.goto("/login");
  await page.getByLabel("Correo o usuario").fill(username);
  await page.getByLabel(/contraseña/i).fill(password);
  await page.getByRole("button", { name: /entrar/i }).click();
}

test.describe("role login redirects", () => {
  test("admin user reaches the admin dashboard", async ({ page }) => {
    await loginAs(page, "demo_admin");
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByRole("heading", { name: /control operativo/i })).toBeVisible();
  });

  test("technician user reaches the technician dashboard", async ({ page }) => {
    await loginAs(page, "tech_carlos");
    await expect(page).toHaveURL(/\/technician$/);
    await expect(page.getByRole("heading", { name: /onboarding y servicios/i })).toBeVisible();
  });

  test("arbiter user reaches the arbiter dashboard", async ({ page }) => {
    await loginAs(page, "demo_arbiter");
    await expect(page).toHaveURL(/\/arbiter$/);
    await expect(page.getByRole("heading", { name: /panel de arbitraje/i })).toBeVisible();
  });
});

test("invalid credentials show an error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Correo o usuario").fill("demo_admin");
  await page.getByLabel(/contraseña/i).fill("wrong-password");
  await page.getByRole("button", { name: /entrar/i }).click();

  await expect(page.getByText(/no se pudo iniciar sesion/i)).toBeVisible();
});
