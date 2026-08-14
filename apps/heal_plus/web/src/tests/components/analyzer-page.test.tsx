import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AnalyzerPage, StandaloneAnalyzerPage } from '../../features/analyzer/AnalyzerPage';

vi.mock('../../components/layout/sidebar', () => ({
  Sidebar: () => <aside>Navigation shell</aside>
}));

vi.mock('../../components/layout/Topbar', () => ({
  Topbar: () => <header>Mobile shell</header>
}));

vi.mock('../../components/heal-analyzer/analyzer-workbench', () => ({
  AnalyzerWorkbench: ({ showSidebarToggle }: { showSidebarToggle?: boolean }) => (
    <main>Analyzer workbench {showSidebarToggle ? 'with navigation control' : ''}</main>
  )
}));

describe('AnalyzerPage', () => {
  it.each([
    ['autenticado', AnalyzerPage],
    ['standalone', StandaloneAnalyzerPage]
  ])('preserva o HEAL Analyzer no modo %s', (_mode, Page) => {
    render(<Page />);

    expect(screen.getByText('Navigation shell')).toBeInTheDocument();
    expect(screen.getByText('Mobile shell')).toBeInTheDocument();
    expect(screen.getByRole('main')).toHaveTextContent('Analyzer workbench with navigation control');
  });
});
