/** Ask Morgan tab — streaming SSE query interface. */

import React, { useState, useRef } from 'react';
import { View, Text, TextInput, FlatList, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Typography, Spacing, Radius } from '../../constants/colors';
import GlassCard from '../../components/ui/GlassCard';
import GradientButton from '../../components/ui/GradientButton';
import { askMorgan } from '../../services/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  isReport?: boolean;
}

export default function MorganScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const send = async () => {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      const data = await askMorgan({ question, market: 'US' });
      const summary = data?.summary || data?.answer || 'No response';
      setMessages((prev) => [...prev, { role: 'assistant', content: summary, isReport: data?.is_report }]);
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Error fetching response. Please try again.' }]);
    }
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.headline}>Ask Morgan</Text>
      <Text style={styles.subtitle}>Senior Equity Research Analyst</Text>

      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        renderItem={({ item }) => (
          <GlassCard style={[styles.msgCard, item.role === 'user' ? styles.userMsg : styles.assistantMsg, item.isReport && styles.reportMsg]}>
            {item.isReport && <Text style={styles.reportBadge}>MORGAN REPORT</Text>}
            <Text style={[styles.msgText, item.role === 'user' && styles.userText]}>{item.content}</Text>
          </GlassCard>
        )}
        ListEmptyComponent={<Text style={styles.placeholder}>Ask Morgan anything about stocks, sectors, or macro.</Text>}
        contentContainerStyle={styles.msgList}
      />

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Ask Morgan..."
          placeholderTextColor={Colors.textDim}
          onSubmitEditing={send}
          editable={!loading}
        />
        <GradientButton title={loading ? '...' : 'Send'} onPress={send} loading={loading} disabled={!input.trim()} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.bg },
  headline: { ...Typography.headline, color: Colors.primary, paddingHorizontal: Spacing.lg, paddingTop: Spacing.lg },
  subtitle: { ...Typography.caption, color: Colors.textMuted, paddingHorizontal: Spacing.lg, marginBottom: Spacing.md },
  msgList: { padding: Spacing.lg, paddingBottom: Spacing.xxl },
  msgCard: { marginBottom: Spacing.sm },
  userMsg: { alignSelf: 'flex-end', maxWidth: '80%', backgroundColor: 'rgba(99,102,241,0.15)' },
  assistantMsg: { alignSelf: 'flex-start', maxWidth: '90%' },
  reportMsg: { borderColor: Colors.primary, borderWidth: 1 },
  reportBadge: { ...Typography.mono, color: Colors.primary, marginBottom: Spacing.xs },
  msgText: { ...Typography.body, color: Colors.text },
  userText: { color: Colors.tertiary },
  placeholder: { ...Typography.body, color: Colors.textDim, textAlign: 'center', marginTop: Spacing.xxl * 2 },
  inputRow: { flexDirection: 'row', gap: Spacing.sm, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md, borderTopWidth: 1, borderTopColor: Colors.border },
  input: { flex: 1, backgroundColor: Colors.bgElevated, borderRadius: Radius.md, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm + 2, color: Colors.text, fontFamily: 'monospace', fontSize: 14 },
});