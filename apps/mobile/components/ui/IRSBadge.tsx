/** IRSBadge — Investment Readiness Score badge with zone color. */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Typography, Spacing, Radius } from '../../constants/colors';

interface Props {
  irsPct: number;
  size?: 'sm' | 'md' | 'lg';
}

function irsColor(irsPct: number): string {
  if (irsPct > 65) return Colors.irsStrong;
  if (irsPct > 45) return Colors.irsModerate;
  if (irsPct > 30) return Colors.irsWeak;
  return Colors.irsVeryWeak;
}

function irsZone(irsPct: number): string {
  if (irsPct > 65) return 'STRONG BUY';
  if (irsPct > 45) return 'MODERATE';
  if (irsPct > 30) return 'WEAK';
  return 'VERY WEAK';
}

export default function IRSBadge({ irsPct, size = 'md' }: Props) {
  const color = irsColor(irsPct);
  const zone = irsZone(irsPct);
  const fontSize = size === 'lg' ? 18 : size === 'md' ? 14 : 11;
  const padV = size === 'lg' ? 8 : size === 'md' ? 6 : 4;
  const padH = size === 'lg' ? 14 : size === 'md' ? 10 : 8;

  return (
    <View style={[styles.container, { borderColor: color, paddingVertical: padV, paddingHorizontal: padH }]}>
      <Text style={[styles.pct, { color, fontSize }]}>{irsPct.toFixed(1)}%</Text>
      <Text style={[styles.zone, { color, fontSize: fontSize - 3 }]}>{zone}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderWidth: 1,
    borderRadius: Radius.md,
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.3)',
  },
  pct: {
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  zone: {
    fontWeight: '600',
    fontFamily: 'monospace',
    letterSpacing: 0.5,
  },
});