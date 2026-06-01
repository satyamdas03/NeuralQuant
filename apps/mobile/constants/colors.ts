/** Obsidian Quantum Design System — NeuralQuant Mobile */

export const Colors = {
  // Background
  bg: '#0f0f1a',
  bgElevated: '#1a1a2e',
  bgCard: '#16162a',

  // Text
  text: '#e0e0ff',
  textMuted: '#8888aa',
  textDim: '#555577',

  // Brand
  primary: '#00ffb2',
  primaryDim: 'rgba(0, 255, 178, 0.15)',
  secondary: '#6366f1',
  secondaryDim: 'rgba(99, 102, 241, 0.15)',
  tertiary: '#c1c1ff',

  // Status
  success: '#22c55e',
  warning: '#eab308',
  danger: '#ef4444',

  // Border
  border: 'rgba(255, 255, 255, 0.08)',
  borderGlow: 'rgba(0, 255, 178, 0.2)',

  // Score colors
  scoreHigh: '#00ffb2',
  scoreMid: '#eab308',
  scoreLow: '#ef4444',

  // IRS zone colors
  irsStrong: '#00ffb2',    // > 65%
  irsModerate: '#eab308',  // 45-65%
  irsWeak: '#f97316',      // 30-45%
  irsVeryWeak: '#ef4444',  // < 30%

  // Glass
  glassBg: 'rgba(22, 22, 42, 0.7)',
  glassBorder: 'rgba(255, 255, 255, 0.06)',
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const Typography = {
  headline: { fontSize: 28, fontWeight: '700' as const, letterSpacing: -0.5 },
  title: { fontSize: 20, fontWeight: '600' as const, letterSpacing: -0.3 },
  subtitle: { fontSize: 16, fontWeight: '500' as const },
  body: { fontSize: 14, fontWeight: '400' as const },
  caption: { fontSize: 12, fontWeight: '400' as const, color: Colors.textMuted },
  mono: { fontSize: 11, fontWeight: '600' as const, fontFamily: 'monospace', letterSpacing: 0.5 },
  monoLarge: { fontSize: 14, fontWeight: '700' as const, fontFamily: 'monospace', letterSpacing: 0.3 },
};

export const Radius = {
  sm: 6,
  md: 10,
  lg: 14,
  xl: 20,
  full: 9999,
};