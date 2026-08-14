import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const PASSWORD = 'Synthetic-password-2026!';

interface SyntheticUser {
  email: string;
  localId: string;
}

async function ensureSyntheticUser(email: string): Promise<SyntheticUser> {
  return {
    email,
    localId: `synthetic-${email.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`
  };
}

async function stubSupabase(
  page: Page,
  user: SyntheticUser,
  options: { includeOwnedPatient?: boolean; requestedUrls?: string[] } = {}
): Promise<void> {
  await page.route('http://127.0.0.1:54321/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    options.requestedUrls?.push(url.toString());

    const authUser = {
      id: user.localId,
      aud: 'authenticated',
      role: 'authenticated',
      email: user.email,
      email_confirmed_at: '2026-07-27T00:00:00Z',
      confirmed_at: '2026-07-27T00:00:00Z',
      last_sign_in_at: '2026-08-03T00:00:00Z',
      app_metadata: { provider: 'email', providers: ['email'] },
      user_metadata: { full_name: 'Profissional Sintético' },
      identities: [],
      created_at: '2026-07-27T00:00:00Z',
      updated_at: '2026-08-03T00:00:00Z',
      is_anonymous: false
    };

    if (url.pathname === '/auth/v1/token') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: `access-${user.localId}`,
          token_type: 'bearer',
          expires_in: 3600,
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          refresh_token: `refresh-${user.localId}`,
          user: authUser
        })
      });
      return;
    }

    if (url.pathname === '/auth/v1/user') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(authUser) });
      return;
    }

    if (url.pathname.includes('/rest/v1/users')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          uid: user.localId,
          display_name: 'Profissional Sintético',
          email: user.email,
          photo_url: null,
          provider_ids: ['password'],
          role: 'professional',
          settings: {},
          professional_area: 'Enfermagem',
          clinic_name: 'Clínica Sintética',
          phone: '',
          onboarding_completed: true,
          created_at: '2026-07-27T00:00:00Z',
          updated_at: '2026-07-27T00:00:00Z'
        })
      });
      return;
    }

    if (url.pathname.includes('/rest/v1/patients')) {
      const requestedId = url.searchParams.get('id');
      const requestedOwner = url.searchParams.get('user_id');
      if (requestedId) {
        if (
          requestedId === 'eq.synthetic-patient-a' &&
          requestedOwner === `eq.${user.localId}` &&
          options.includeOwnedPatient
        ) {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 'synthetic-patient-a',
              user_id: user.localId,
              name: 'Paciente Sintético A',
              phone: '',
              email: '',
              birth_date: '',
              notes: '',
              archived: false
            })
          });
          return;
        }
        await route.fulfill({
          status: 406,
          contentType: 'application/json',
          body: JSON.stringify({ code: 'PGRST116', message: 'resource not available' })
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          options.includeOwnedPatient
            ? [
                {
                  id: 'synthetic-patient-a',
                  user_id: user.localId,
                  name: 'Paciente Sintético A',
                  phone: '',
                  email: '',
                  birth_date: '',
                  notes: '',
                  archived: false
                }
              ]
            : []
        )
      });
      return;
    }

    if (
      url.pathname.includes('/rest/v1/evaluations') ||
      url.pathname.includes('/rest/v1/appointments')
    ) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]'
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]'
    });
  });
}

async function login(page: Page, user: SyntheticUser): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('E-mail').fill(user.email);
  await page.getByLabel('Senha', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: /^Entrar$/ }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function connectSyntheticGoogleProvider(page: Page): Promise<void> {
  await page.goto('/chat');
  await page.getByLabel('Chave de API').fill('synthetic-provider-key');
  await page.getByRole('button', { name: 'Salvar e usar' }).click();
  await expect(page.getByLabel('Mensagem para o assistente')).toBeEnabled();
}

test('abre a tela de login', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('button', { name: /^Entrar$/ })).toBeVisible();
});

test('não envia contexto clínico após cancelamento do consentimento', async ({ page }) => {
  const user = await ensureSyntheticUser('e2e-consent@healplus.invalid');
  await stubSupabase(page, user, { includeOwnedPatient: true });
  let providerBody = '';
  let providerRequests = 0;
  await page.route('https://generativelanguage.googleapis.com/**', async route => {
    providerRequests += 1;
    providerBody = route.request().postData() ?? '';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        candidates: [{ content: { parts: [{ text: 'Orientação geral segura.' }] } }]
      })
    });
  });
  await login(page, user);
  await connectSyntheticGoogleProvider(page);

  const prompt = 'Forneça uma orientação geral.';
  await page.getByLabel('Mensagem para o assistente').fill(prompt);
  await page.getByLabel('Enviar mensagem').click();
  await expect(page.getByRole('heading', { name: 'Compartilhar dados com a IA?' })).toBeVisible();
  await expect(page.getByText('Destino: https://generativelanguage.googleapis.com/v1beta')).toBeVisible();
  await expect(page.getByText(/Identidade e contexto do paciente não serão enviados/i)).toBeVisible();
  await page.getByRole('button', { name: 'Manter sem enviar' }).click();

  expect(providerRequests).toBe(0);
  await expect(page.getByLabel('Mensagem para o assistente')).toHaveValue(prompt);

  await page.getByLabel('Enviar mensagem').click();
  await page.getByRole('button', { name: 'Autorizar e enviar uma vez' }).click();

  await expect(page.getByText('Orientação geral segura.')).toBeVisible();
  expect(providerRequests).toBe(1);
  expect(providerBody).toContain(prompt);
  expect(providerBody).not.toContain('Paciente Sintético A');
});

test('stepper é acessível por tecnologia assistiva e respeita movimento reduzido', async ({ page }) => {
  const user = await ensureSyntheticUser('e2e-stepper-a11y@healplus.invalid');
  await stubSupabase(page, user, { includeOwnedPatient: true });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await login(page, user);
  await page.goto('/evaluations/new');

  const progress = page.getByRole('navigation', { name: 'Progresso da avaliação clínica' });
  await expect(progress).toBeVisible();
  await expect(progress.locator('[aria-current="step"]')).toContainText('Paciente');

  const results = await new AxeBuilder({ page }).include('form').analyze();
  expect(results.violations.filter(item => ['serious', 'critical'].includes(item.impact ?? ''))).toEqual([]);

  const transitionDuration = await progress.locator('[aria-current="step"]').evaluate(element =>
    getComputedStyle(element).transitionDuration
  );
  expect(transitionDuration).toBe('0s');
});

test('sessão ausente em deep link não mostra nem mantém conteúdo da conta anterior', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('redisus-ai-credential-v1:previous-user', 'synthetic-secret');
    sessionStorage.setItem('redisus-chat-history-v2:previous-user', 'synthetic-clinical-draft');
    sessionStorage.setItem('healplus_ai_chat_sessions_v3:previous-user', 'synthetic-clinical-draft-v3');
    sessionStorage.setItem('healplus_ai_consent_log_v1:previous-user', 'synthetic-consent-receipt');
  });

  await page.goto('/patients/synthetic-patient-a');

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Paciente Sintético A')).toHaveCount(0);
  const sensitiveKeys = await page.evaluate(() =>
    Object.keys(sessionStorage).filter(
      key =>
        key.startsWith('redisus-ai-credential') ||
        key.startsWith('redisus-chat-history') ||
        key.startsWith('healplus_ai_chat_sessions') ||
        key.startsWith('healplus_ai_consent_log')
    )
  );
  expect(sensitiveKeys).toEqual([]);
});

test('identificador de outro usuário é negado sem revelar a existência do recurso', async ({ page }) => {
  const user = await ensureSyntheticUser('e2e-cross-user@healplus.invalid');
  const requestedUrls: string[] = [];
  await stubSupabase(page, user, { requestedUrls });
  await login(page, user);

  await page.goto('/patients/synthetic-patient-a');

  await expect(page.getByText('Paciente não encontrado')).toBeVisible();
  await expect(page.getByText('Paciente Sintético A')).toHaveCount(0);
  expect(
    requestedUrls.some(url =>
      url.includes('id=eq.synthetic-patient-a') &&
      url.includes(`user_id=eq.${encodeURIComponent(user.localId)}`)
    )
  ).toBeTruthy();
});

test('falha do provedor preserva a mensagem e não ecoa segredo ou dado clínico', async ({ page }) => {
  const user = await ensureSyntheticUser('e2e-provider-failure@healplus.invalid');
  await stubSupabase(page, user, { includeOwnedPatient: true });
  await page.route('https://generativelanguage.googleapis.com/**', async route => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          message: 'synthetic-provider-key Paciente Sintético A internal prompt'
        }
      })
    });
  });
  await login(page, user);
  await connectSyntheticGoogleProvider(page);

  const prompt = 'Rascunho sintético para tentar novamente';
  await page.getByLabel('Mensagem para o assistente').fill(prompt);
  await page.getByLabel('Enviar mensagem').click();
  await page.getByRole('button', { name: 'Autorizar e enviar uma vez' }).click();

  await expect(page.getByText(prompt)).toBeVisible();
  await expect(page.getByText(/provedor não conseguiu concluir/i)).toBeVisible();
  await expect(page.getByText('synthetic-provider-key')).toHaveCount(0);
  const pageText = await page.locator('body').innerText();
  expect(pageText).not.toContain('internal prompt');
});
