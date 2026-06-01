/** Root layout — Expo Router entry point. */

import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Colors } from '../constants/colors';

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: Colors.bg },
          headerTintColor: Colors.text,
          headerTitleStyle: { fontFamily: 'monospace', fontSize: 13, fontWeight: '600' },
          contentStyle: { backgroundColor: Colors.bg },
          animation: 'slide_from_right',
        }}
      >
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="stock/[ticker]" options={{ title: 'Stock Detail' }} />
        <Stack.Screen name="analyst/[ticker]" options={{ title: 'PARA-DEBATE' }} />
        <Stack.Screen name="astra/index" options={{ title: 'QuantAstra' }} />
      </Stack>
    </>
  );
}