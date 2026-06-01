/** Dashboard tab — movers, indices, watchlist strip. */

import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, StyleSheet, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing, Radius } from '../../constants/colors';
import GlassCard from '../../components/ui/GlassCard';
import ScoreBadge from '../../components/ui/ScoreBadge';
import { fetchMarketMovers, fetchMarketTrending } from '../../services/api';

export default function DashboardScreen() {
  const [movers, setMovers] = useState<any>(null);
  const [trending, setTrending] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const [m, t] = await Promise.all([fetchMarketMovers(), fetchMarketTrending(10)]);
      setMovers(m);
      setTrending(t?.leaders || t || []);
    } catch {}
  };

  useEffect(() => { load(); }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.headline}>NeuralQuant</Text>
      <Text style={styles.subtitle}>AI Stock Intelligence</Text>

      <GlassCard glow style={styles.section}>
        <Text style={styles.sectionTitle}>Market Movers</Text>
        {movers ? (
          <Text style={styles.body}>Live market data loaded</Text>
        ) : (
          <Text style={styles.muted}>Loading market data...</Text>
        )}
      </GlassCard>

      <GlassCard style={styles.section}>
        <Text style={styles.sectionTitle}>IRS Leaders</Text>
        <FlatList
          data={trending}
          keyExtractor={(item, i) => item?.ticker || String(i)}
          renderItem={({ item }) => (
            <View style={styles.trendingRow}>
              <Text style={styles.tickerText}>{item?.ticker || '—'}</Text>
              {item?.irs_pct != null && (
                <Text style={[styles.irsText, { color: item.irs_pct > 65 ? Colors.irsStrong : item.irs_pct > 45 ? Colors.irsModerate : Colors.irsWeak }]}>
                  {item.irs_pct.toFixed(1)}%
                </Text>
              )}
              {item?.composite_anjali_score != null && <ScoreBadge score={item.composite_anjali_score / 2} size={28} />}
            </View>
          )}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary} />}
          ListEmptyComponent={<Text style={styles.muted}>No trending data</Text>}
        />
      </GlassCard>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg, padding: Spacing.lg },
  headline: { ...Typography.headline, color: Colors.primary },
  subtitle: { ...Typography.caption, color: Colors.textMuted, marginBottom: Spacing.xl },
  section: { marginBottom: Spacing.lg },
  sectionTitle: { ...Typography.mono, color: Colors.tertiary, marginBottom: Spacing.sm },
  body: { ...Typography.body, color: Colors.text },
  muted: { ...Typography.body, color: Colors.textDim },
  trendingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: Spacing.sm },
  tickerText: { ...Typography.monoLarge, color: Colors.text },
  irsText: { fontFamily: 'monospace', fontSize: 13, fontWeight: '700' },
});