/** Stock detail screen — Anjali scores, IRS, price. */

import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../../constants/colors';
import GlassCard from '../../components/ui/GlassCard';
import ScoreBadge from '../../components/ui/ScoreBadge';
import IRSBadge from '../../components/ui/IRSBadge';
import GradientButton from '../../components/ui/GradientButton';
import { fetchStockAnjali } from '../../services/api';

export default function StockDetailScreen() {
  const { ticker } = useLocalSearchParams<{ ticker: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (ticker) {
      fetchStockAnjali(ticker)
        .then(setData)
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [ticker]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color={Colors.primary} size="large" style={styles.loader} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView>
        <View style={styles.header}>
          <Text style={styles.headline}>{ticker}</Text>
          <Text style={styles.nameText}>{data?.name || ''}</Text>
        </View>

        {data?.irs_pct != null && (
          <GlassCard glow style={styles.section}>
            <Text style={styles.sectionTitle}>INVESTMENT READINESS SCORE</Text>
            <IRSBadge irsPct={data.irs_pct} size="lg" />
          </GlassCard>
        )}

        {data?.composite_anjali_score != null && (
          <GlassCard style={styles.section}>
            <Text style={styles.sectionTitle}>AI COMPOSITE SCORE</Text>
            <ScoreBadge score={data.composite_anjali_score / 2} size={48} />
          </GlassCard>
        )}

        <GlassCard style={styles.section}>
          <Text style={styles.sectionTitle}>ANJALI FACTORS</Text>
          {data?.g_score != null && <Text style={styles.factorText}>G Score: {data.g_score.toFixed(1)}</Text>}
          {data?.risk_eff_score != null && <Text style={styles.factorText}>Risk Efficiency: {data.risk_eff_score.toFixed(1)}</Text>}
          {data?.growth_score != null && <Text style={styles.factorText}>Growth: {data.growth_score.toFixed(1)}</Text>}
          {data?.return_score != null && <Text style={styles.factorText}>Return: {data.return_score.toFixed(1)}</Text>}
          {data?.valuation_score != null && <Text style={styles.factorText}>Valuation: {data.valuation_score.toFixed(1)}</Text>}
          {data?.risk_score != null && <Text style={styles.factorText}>Risk: {data.risk_score.toFixed(1)}</Text>}
        </GlassCard>

        {data?.irs_interpretation && (
          <GlassCard style={styles.section}>
            <Text style={styles.sectionTitle}>IRS INTERPRETATION</Text>
            <Text style={styles.body}>{data.irs_interpretation}</Text>
          </GlassCard>
        )}

        <Text style={styles.disclaimer}>This is AI-generated investment research, not SEBI-registered investment advice.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg, padding: Spacing.lg },
  header: { marginBottom: Spacing.lg },
  headline: { ...Typography.headline, color: Colors.primary },
  nameText: { ...Typography.body, color: Colors.textMuted },
  section: { marginBottom: Spacing.lg },
  sectionTitle: { ...Typography.mono, color: Colors.tertiary, marginBottom: Spacing.sm },
  factorText: { ...Typography.monoLarge, color: Colors.text, marginBottom: Spacing.xs },
  body: { ...Typography.body, color: Colors.text },
  loader: { marginTop: 100 },
  disclaimer: { ...Typography.caption, color: Colors.textDim, textAlign: 'center', marginTop: Spacing.xl, fontStyle: 'italic' },
});