import { describe, expect, it } from 'vitest';

import { friendlyAuthError } from '../../features/auth/authService';

describe('friendlyAuthError', () => {
  it('usa a mesma resposta para credenciais inválidas sem enumerar contas', () => {
    const message = 'E-mail ou senha incorretos.';

    expect(friendlyAuthError({ code: 'auth/user-not-found' })).toBe(message);
    expect(friendlyAuthError({ code: 'auth/wrong-password' })).toBe(message);
    expect(friendlyAuthError({ code: 'auth/invalid-credential' })).toBe(message);
    expect(friendlyAuthError({ code: 'auth/user-disabled' })).toBe(message);
  });

  it('não confirma a existência de conta no cadastro ou login social', () => {
    expect(friendlyAuthError({ code: 'auth/email-already-in-use' })).toBe(
      'Não foi possível criar a conta com os dados informados.'
    );
    expect(friendlyAuthError({ code: 'auth/account-exists-with-different-credential' })).toBe(
      'Não foi possível concluir a autenticação com esse provedor.'
    );
  });

  it('traduz erros operacionais comuns do Firebase Auth', () => {
    expect(friendlyAuthError({ code: 'auth/popup-closed-by-user' })).toBe('Login cancelado antes da conclusão.');
    expect(friendlyAuthError({ code: 'auth/unauthorized-domain' })).toBe('Este domínio não está autorizado no Firebase Auth.');
  });
});
