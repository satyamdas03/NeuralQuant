/** ScoreBadge — 1-10 circular badge with color coding. */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Typography, Spacing } from '../../constants/colors';

interface Props {
  score: number;
  size?: number;
}

function scoreColor(score: number): string {
  if (score >= 7) return Colors.scoreHigh;
  if (score >= 4) return Colors.scoreMid;
  return Colors.scoreLow;
}

export default function ScoreBadge({ score, size = 36 }: Props) {
  const color = scoreColor(score);
  return (
    <View style={[styles.badge, { width: size, height: size, borderRadius: size / 2, borderColor: color }]}>
      <Text style={[styles.text, { color }}>{score.toFixed(1)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.3)',
  },
  text: {
    fontSize: 12,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
});