/** Sign in screen. */

import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing, Radius } from '../../constants/colors';
import GlassCard from '../../components/ui/GlassCard';
import GradientButton from '../../components/ui/GradientButton';
import { signIn } from '../../services/supabase';
import { useAuthStore } from '../../store';
import { useRouter } from 'expo-router';

export default function SignInScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { setAuth } = useAuthStore();
  const router = useRouter();

  const handleSignIn = async () => {
    setLoading(true);
    setError('');
    try {
      const { data, error: e } = await signIn(email, password);
      if (e) { setError(e.message); return; }
      if (data.user) {
        setAuth(data.user.id, data.user.email || '');
        router.replace('/(tabs)');
      }
    } catch { setError('Sign in failed'); }
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.headline}>NeuralQuant</Text>
      <Text style={styles.subtitle}>Sign in to your account</Text>
      <GlassCard style={styles.card}>
        <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="Email" placeholderTextColor={Colors.textDim} autoCapitalize="none" keyboardType="email-address" />
        <TextInput style={styles.input} value={password} onChangeText={setPassword} placeholder="Password" placeholderTextColor={Colors.textDim} secureTextEntry />
        {error && <Text style={styles.error}>{error}</Text>}
        <GradientButton title="Sign In" onPress={handleSignIn} loading={loading} />
      </GlassCard>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg, justifyContent: 'center', padding: Spacing.xl },
  headline: { ...Typography.headline, color: Colors.primary, textAlign: 'center' },
  subtitle: { ...Typography.caption, color: Colors.textMuted, textAlign: 'center', marginBottom: Spacing.xxl },
  card: { marginBottom: Spacing.lg },
  input: { backgroundColor: Colors.bgElevated, borderRadius: Radius.md, paddingHorizontal: Spacing.md, paddingVertical: Spacing.md, color: Colors.text, marginBottom: Spacing.md, fontFamily: 'monospace' },
  error: { color: Colors.danger, marginBottom: Spacing.sm, fontFamily: 'monospace', fontSize: 12 },
});