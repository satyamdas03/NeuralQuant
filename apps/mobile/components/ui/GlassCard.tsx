/** GlassCard — blur + border, Obsidian Quantum style. */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { BlurView } from 'expo-blur';
import { Colors, Radius, Spacing } from '../../constants/colors';

interface Props {
  children: React.ReactNode;
  style?: any;
  glow?: boolean;
}

export default function GlassCard({ children, style, glow }: Props) {
  return (
    <BlurView intensity={20} tint="dark" style={[styles.container, glow && styles.glow, style]}>
      {children}
    </BlurView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.glassBg,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.glassBorder,
    padding: Spacing.lg,
    overflow: 'hidden',
  },
  glow: {
    borderColor: Colors.borderGlow,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowRadius: 12,
    shadowOpacity: 0.15,
  },
});