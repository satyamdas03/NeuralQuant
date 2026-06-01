/** Screener tab — filter stocks by AI scores. */

import React, { useState } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../../constants/colors';
import GlassCard from '../../components/ui/GlassCard';
import ScoreBadge from '../../components/ui/ScoreBadge';
import { fetchScreenerResults } from '../../services/api';
import { useRouter } from 'expo-router';

export default function ScreenerScreen() {
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [market, setMarket] = useState<'US' | 'IN'>('US');
  const router = useRouter();

  const runScreener = async () => {
    setLoading(true);
    try {
      const data = await fetchScreenerResults({ market, limit: 20 });
      setResults(data?.stocks || data?.results || []);
    } catch {}
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.headline}>AI Screener</Text>
      <View style={styles.marketToggle}>
        {(['US', 'IN'] as const).map((m) => (
          <TouchableOpacity key={m} onPress={() => setMarket(m)} style={[styles.marketBtn, market === m && styles.marketActive]}>
            <Text style={[styles.marketText, market === m && styles.marketTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <TouchableOpacity style={styles.runBtn} onPress={runScreener} disabled={loading}>
        <Text style={styles.runText}>{loading ? 'Scanning...' : 'Run Screener'}</Text>
      </TouchableOpacity>
      <FlatList
        data={results}
        keyExtractor={(item, i) => item?.ticker || String(i)}
        renderItem={({ item }) => (
          <GlassCard style={styles.resultRow}>
            <TouchableOpacity onPress={() => router.push(`/stock/${item.ticker}`)}>
              <View style={styles.resultContent}>
                <View>
                  <Text style={styles.tickerText}>{item.ticker}</Text>
                  <Text style={styles.sectorText}>{item.sector || '—'}</Text>
                </View>
                {item.score_1_10 != null && <ScoreBadge score={item.score_1_10} />}
              </View>
            </TouchableOpacity>
          </GlassCard>
        )}
        ListEmptyComponent={<Text style={styles.muted}>Tap "Run Screener" to find stocks</Text>}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg, padding: Spacing.lg },
  headline: { ...Typography.headline, color: Colors.text, marginBottom: Spacing.lg },
  marketToggle: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md },
  marketBtn: { paddingHorizontal: Spacing.lg, paddingVertical: Spacing.sm, borderRadius: 8, borderWidth: 1, borderColor: Colors.border },
  marketActive: { backgroundColor: Colors.primaryDim, borderColor: Colors.primary },
  marketText: { fontFamily: 'monospace', fontSize: 12, color: Colors.textMuted },
  marketTextActive: { color: Colors.primary },
  runBtn: { backgroundColor: Colors.primary, paddingVertical: Spacing.md, borderRadius: 10, alignItems: 'center', marginBottom: Spacing.lg },
  runText: { fontFamily: 'monospace', fontSize: 13, fontWeight: '700', color: Colors.bg },
  resultRow: { marginBottom: Spacing.sm },
  resultContent: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  tickerText: { ...Typography.monoLarge, color: Colors.text },
  sectorText: { ...Typography.caption, color: Colors.textDim },
  muted: { ...Typography.body, color: Colors.textDim, textAlign: 'center', marginTop: Spacing.xxl },
});