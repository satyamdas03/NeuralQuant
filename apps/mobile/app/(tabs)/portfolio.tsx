/** Portfolio tab — IRS assessment, sell signals, risk profiling. */

import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../../constants/colors';
import GlassCard from '../../components/ui/GlassCard';
import IRSBadge from '../../components/ui/IRSBadge';
import GradientButton from '../../components/ui/GradientButton';
import { fetchSellSignals, fetchAstraRecommend, saveRiskProfile } from '../../services/api';
import { useAuthStore, useRiskProfileStore, usePortfolioStore } from '../../store';
import { useRouter } from 'expo-router';

export default function PortfolioScreen() {
  const { isSignedIn } = useAuthStore();
  const { riskProfile, setRiskProfile } = useRiskProfileStore();
  const { holdings, isLoading } = usePortfolioStore();
  const [sellSignals, setSellSignals] = useState<any>(null);
  const [recommendation, setRecommendation] = useState<any>(null);
  const router = useRouter();

  useEffect(() => {
    if (isSignedIn) { fetchSellSignals().then(setSellSignals).catch(() => {}); }
  }, [isSignedIn]);

  const getRecommendation = async (profile: string) => {
    setRiskProfile(profile as any);
    try {
      const data = await fetchAstraRecommend(profile);
      setRecommendation(data);
    } catch {}
  };

  if (!isSignedIn) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.headline}>Portfolio</Text>
        <GlassCard style={styles.emptyCard}>
          <Text style={styles.muted}>Sign in to access your portfolio, IRS assessment, and QuantAstra recommendations.</Text>
        </GlassCard>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.headline}>Portfolio</Text>

      {sellSignals?.hard_sell_count > 0 && (
        <GlassCard glow style={styles.warningCard}>
          <Text style={styles.warningTitle}>SELL SIGNALS</Text>
          <Text style={styles.warningText}>{sellSignals.hard_sell_count} position(s) flagged</Text>
        </GlassCard>
      )}

      {!riskProfile ? (
        <GlassCard style={styles.section}>
          <Text style={styles.sectionTitle}>RISK PROFILE</Text>
          <Text style={styles.body}>Before QuantAstra can recommend a portfolio, we need your risk tolerance.</Text>
          <View style={styles.riskButtons}>
            <GradientButton title="Conservative" onPress={() => getRecommendation('low')} variant="ghost" />
            <GradientButton title="Growth" onPress={() => getRecommendation('high')} variant="secondary" />
            <GradientButton title="Aggressive" onPress={() => getRecommendation('very_high')} variant="primary" />
          </View>
        </GlassCard>
      ) : (
        <GlassCard style={styles.section}>
          <View style={styles.profileRow}>
            <Text style={styles.sectionTitle}>RISK PROFILE: {riskProfile.toUpperCase()}</Text>
            <TouchableOpacity onPress={() => setRecommendation(null)}>
              <Text style={styles.changeText}>change</Text>
            </TouchableOpacity>
          </View>
        </GlassCard>
      )}

      {recommendation && (
        <GlassCard style={styles.section}>
          <Text style={styles.sectionTitle}>QUANTASTRA RECOMMENDATION</Text>
          <FlatList
            data={recommendation?.stocks || []}
            keyExtractor={(item, i) => item?.ticker || String(i)}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.stockRow} onPress={() => router.push(`/stock/${item.ticker}`)}>
                <View>
                  <Text style={styles.tickerText}>{item.ticker}</Text>
                  <Text style={styles.sectorText}>{item.sector || ''}</Text>
                </View>
                {item.irs_pct != null && <IRSBadge irsPct={item.irs_pct} size="sm" />}
              </TouchableOpacity>
            )}
          />
        </GlassCard>
      )}

      <Text style={styles.disclaimer}>This is AI-generated investment research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing.</Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg, padding: Spacing.lg },
  headline: { ...Typography.headline, color: Colors.text, marginBottom: Spacing.lg },
  section: { marginBottom: Spacing.lg },
  sectionTitle: { ...Typography.mono, color: Colors.tertiary, marginBottom: Spacing.sm },
  body: { ...Typography.body, color: Colors.text, marginBottom: Spacing.md },
  muted: { ...Typography.body, color: Colors.textDim, textAlign: 'center' },
  emptyCard: { marginTop: Spacing.xxl * 2 },
  warningCard: { marginBottom: Spacing.lg, borderColor: Colors.danger },
  warningTitle: { ...Typography.mono, color: Colors.danger },
  warningText: { ...Typography.body, color: Colors.text },
  riskButtons: { flexDirection: 'row', gap: Spacing.sm, flexWrap: 'wrap' },
  profileRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  changeText: { ...Typography.caption, color: Colors.primary },
  stockRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: Spacing.sm, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tickerText: { ...Typography.monoLarge, color: Colors.text },
  sectorText: { ...Typography.caption, color: Colors.textDim },
  disclaimer: { ...Typography.caption, color: Colors.textDim, textAlign: 'center', marginTop: Spacing.xl, fontStyle: 'italic' },
});