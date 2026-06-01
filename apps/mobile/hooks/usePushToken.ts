/** Register Expo push token with backend for notifications. */

import { useEffect } from 'react';
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { registerPushToken } from '../services/api';
import { useAuthStore } from '../store';

export function usePushToken() {
  const { isSignedIn } = useAuthStore();

  useEffect(() => {
    if (!isSignedIn) return;

    (async () => {
      try {
        const { status } = await Notifications.requestPermissionsAsync();
        if (status !== 'granted') return;

        const token = await Notifications.getExpoPushTokenAsync({
          projectId: process.env.EXPO_PUBLIC_PROJECT_ID,
        });

        if (token.data) {
          const platform = Platform.OS === 'ios' ? 'ios' : 'android';
          await registerPushToken(token.data, platform);
        }
      } catch {}
    })();
  }, [isSignedIn]);
}