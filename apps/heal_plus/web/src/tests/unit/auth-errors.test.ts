import { describe, expect, it } from 'vitest';

import { friendlyAuthError } from '../../features/auth/authService';

describe('friendlyAuthError', () => {
  it('usa a mesma resposta para credenciais inválidas sem enumerar contas', () => {
    const expected = 'E-mail ou senha incorretos.';

    expect(friendlyAuthError({ message: 'Invalid login credentials' })).toBe(expected);
    expect(friendlyAuthError({ message: 'invalid_credentials' })).toBe(expected);
  });

  it('não confirma a existência de conta no cadastro', () => {
    expect(friendlyAuthError({ message: 'User already registered' })).toBe(
      'Não foi possível criar a conta com os dados informados.'
    );
    expect(friendlyAuthError({ message: 'User has already been registered' })).toBe(
      'Não foi possível criar a conta com os dados informados.'
    );
  });

  it('traduz erros operacionais comuns de autenticação', () => {
    expect(friendlyAuthError({ message: 'popup cancelled' })).toBe('Login cancelado antes da conclusão.');
    expect(friendlyAuthError({ message: 'network fetch error' })).toBe('Falha de rede. Verifique sua conexão.');
  });
});
