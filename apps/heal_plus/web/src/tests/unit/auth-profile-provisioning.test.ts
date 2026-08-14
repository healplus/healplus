import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const maybeSingle = vi.fn();
  const selectEq = vi.fn(() => ({ maybeSingle }));
  const select = vi.fn(() => ({ eq: selectEq }));
  const insert = vi.fn().mockResolvedValue({ error: null });
  const updateEq = vi.fn().mockResolvedValue({ error: null });
  const update = vi.fn(() => ({ eq: updateEq }));

  return {
    maybeSingle,
    select,
    insert,
    update,
    updateEq,
    from: vi.fn(() => ({ select, insert, update })),
    getUser: vi.fn()
  };
});

vi.mock('../../lib/supabase', () => ({
  supabase: {
    from: mocks.from,
    auth: { getUser: mocks.getUser }
  }
}));

import { updateUserProfile } from '../../features/auth/authService';

describe('updateUserProfile', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.maybeSingle.mockResolvedValue({ data: null, error: null });
    mocks.insert.mockResolvedValue({ error: null });
    mocks.updateEq.mockResolvedValue({ error: null });
    mocks.getUser.mockResolvedValue({
      data: {
        user: {
          email: 'profissional@example.test',
          user_metadata: { full_name: 'Profissional Sintético' },
          app_metadata: { providers: ['email'] }
        }
      }
    });
  });

  it('provisiona um perfil completo antes de aplicar atualização parcial', async () => {
    await updateUserProfile('user-a', {
      displayName: 'Profissional Sintético',
      professionalArea: 'Enfermagem',
      onboardingCompleted: true
    });

    expect(mocks.insert).toHaveBeenCalledWith(
      expect.objectContaining({
        uid: 'user-a',
        email: 'profissional@example.test',
        display_name: 'Profissional Sintético',
        professional_area: 'Enfermagem',
        onboarding_completed: true
      })
    );
    expect(mocks.update).toHaveBeenCalledWith(
      expect.objectContaining({
        display_name: 'Profissional Sintético',
        professional_area: 'Enfermagem',
        onboarding_completed: true
      })
    );
    expect(mocks.updateEq).toHaveBeenCalledWith('uid', 'user-a');
  });

  it('não insere novamente quando o perfil já existe', async () => {
    mocks.maybeSingle.mockResolvedValueOnce({ data: { uid: 'user-a' }, error: null });

    await updateUserProfile('user-a', { phone: '11999990000' });

    expect(mocks.insert).not.toHaveBeenCalled();
    expect(mocks.update).toHaveBeenCalledWith(
      expect.objectContaining({ phone: '11999990000' })
    );
  });
});
