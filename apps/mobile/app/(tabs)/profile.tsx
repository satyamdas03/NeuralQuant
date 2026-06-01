/** Profile tab — settings, risk profile, sign out. */

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing } from '../../constants/colors';
import GlassCard from '../../components/ui/GlassCard';
import GradientButton from '../../components/ui/GradientButton';
import { useAuthStore, useRiskProfileStore } from '../../store';
import { signOut } from '../../services/supabase';

export default function ProfileScreen() {
  const { isSignedIn, email, clear: clearAuth } = useAuthStore();
  const { riskProfile, setRiskProfile } = useRiskProfileStore();

  const handleSignOut = async () => {
    await signOut();
    clearAuth();
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.headline}>Profile</Text>

      <GlassCard style={styles.section}>
        <Text style={styles.sectionTitle}>ACCOUNT</Text>
        <Text style={styles.body}>{isSignedIn ? email || 'Signed in' : 'Guest'}</Text>
        {isSignedIn && (
          <GradientButton title="Sign Out" onPress={handleSignOut} variant="ghost" />
        )}
      </GlassCard>

      <GlassCard style={styles.section}>
        <Text style={styles.sectionTitle}>RISK PROFILE</Text>
        <Text style={styles.body}>
          {riskProfile ? `Current: ${riskProfile.toUpperCase()}` : 'Not set — configure in Portfolio tab'}
        </Text>
        {riskProfile && (
          <View style={styles.riskButtons}>
            {(['low', 'high', 'very_high'] as const).map((p) => (
              <TouchableOpacity
                key={p}
                style={[styles.riskBtn, riskProfile === p && styles.riskBtnActive]}
                onPress={() => setRiskProfile(p)}
              >
                <Text style={[styles.riskText, riskProfile === p && styles.riskTextActive]}>{p === 'low' ? 'Conservative' : p === 'high' ? 'Growth' : 'Aggressive'}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </GlassCard>

      <GlassCard style={styles.section}>
        <Text style={styles.sectionTitle}>NEURALQUANT</Text>
        <Text style={styles.muted}>Version 1.0.0</Text>
        <Text style={styles.muted}>co.neuralquant.app</Text>
      </GlassCard>

      <Text style={styles.disclaimer}>This is AI-generated investment research, not SEBI-registered investment advice.</Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg, padding: Spacing.lg },
  headline: { ...Typography.headline, color: Colors.text, marginBottom: Spacing.lg },
  section: { marginBottom: Spacing.lg },
  sectionTitle: { ...Typography.mono, color: Colors.tertiary, marginBottom: Spacing.sm },
  body: { ...Typography.body, color: Colors.text, marginBottom: Spacing.md },
  muted: { ...Typography.caption, color: Colors.textDim },
  riskButtons: { flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.sm },
  riskBtn: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, borderRadius: 8, borderWidth: 1, borderColor: Colors.border },
  riskBtnActive: { backgroundColor: Colors.primaryDim, borderColor: Colors.primary },
  riskText: { fontFamily: 'monospace', fontSize: 11, color: Colors.textMuted },
  riskTextActive: { color: Colors.primary },
  disclaimer: { ...Typography.caption, color: Colors.textDim, textAlign: 'center', marginTop: Spacing.xl, fontStyle: 'italic' },
});