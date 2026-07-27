import { expect, request as playwrightRequest, test, type Page } from '@playwright/test';

const AUTH_EMULATOR =
  'http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts';
const PASSWORD = 'Synthetic-password-2026!';

interface SyntheticUser {
  email: string;
  localId: string;
}

async function ensureSyntheticUser(email: string): Promise<SyntheticUser> {
  const api = await playwrightRequest.newContext();
  try {
    const signUp = await api.post(`${AUTH_EMULATOR}:signUp?key=demo-key`, {
      data: {
        email,
        password: PASSWORD,
        returnSecureToken: true
      }
    });
    if (signUp.ok()) {
      const payload = await signUp.json();
      return { email, localId: String(payload.localId) };
    }

    const signIn = await api.post(`${AUTH_EMULATOR}:signInWithPassword?key=demo-key`, {
      data: {
        email,
        password: PASSWORD,
        returnSecureToken: true
      }
    });
    expect(signIn.ok()).toBeTruthy();
    const payload = await signIn.json();
    return { email, localId: String(payload.localId) };
  } finally {
    await api.dispose();
  }
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
  await page.getByLabel('Senha').fill(PASSWORD);
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
  await page.route('https://generativelanguage.googleapis.com/**', async route => {
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

  await page.getByRole('button', { name: 'Sem dados clínicos' }).click();
  await expect(page.getByRole('heading', { name: 'Compartilhar contexto clínico?' })).toBeVisible();
  await page.getByRole('button', { name: 'Cancelar' }).click();
  await page.getByLabel('Mensagem para o assistente').fill('Forneça uma orientação geral.');
  await page.getByLabel('Enviar mensagem').click();

  await expect(page.getByText('Orientação geral segura.')).toBeVisible();
  expect(providerBody).toContain('O acesso aos registros clínicos está desligado');
  expect(providerBody).not.toContain('Paciente Sintético A');
});

test('sessão ausente em deep link não mostra nem mantém conteúdo da conta anterior', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('redisus-ai-credential-v1:previous-user', 'synthetic-secret');
    sessionStorage.setItem('redisus-chat-history-v2:previous-user', 'synthetic-clinical-draft');
  });

  await page.goto('/patients/synthetic-patient-a');

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Paciente Sintético A')).toHaveCount(0);
  const sensitiveKeys = await page.evaluate(() =>
    Object.keys(sessionStorage).filter(
      key => key.startsWith('redisus-ai-credential') || key.startsWith('redisus-chat-history')
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

  await expect(page.getByText(prompt)).toBeVisible();
  await expect(page.getByText(/provedor não conseguiu concluir/i)).toBeVisible();
  await expect(page.getByText('synthetic-provider-key')).toHaveCount(0);
  const pageText = await page.locator('body').innerText();
  expect(pageText).not.toContain('internal prompt');
});
