/** Tab layout — 5 tabs: Dashboard, Screener, Ask Morgan, Portfolio, Profile. */

import { Tabs } from 'expo-router';
import { LayoutDashboard, ScanSearch, MessageSquareText, PieChart, User } from 'lucide-react-native';
import { Colors } from '../../constants/colors';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: Colors.bg },
        headerTintColor: Colors.text,
        headerTitleStyle: { fontFamily: 'monospace', fontSize: 13, fontWeight: '600' },
        tabBarStyle: {
          backgroundColor: Colors.bgElevated,
          borderTopColor: Colors.border,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 6,
        },
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.textMuted,
        tabBarLabelStyle: { fontFamily: 'monospace', fontSize: 10, fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: 'Dashboard', tabBarIcon: ({ color }) => <LayoutDashboard size={20} color={color} /> }}
      />
      <Tabs.Screen
        name="screener"
        options={{ title: 'Screener', tabBarIcon: ({ color }) => <ScanSearch size={20} color={color} /> }}
      />
      <Tabs.Screen
        name="morgan"
        options={{ title: 'Morgan', tabBarIcon: ({ color }) => <MessageSquareText size={20} color={color} /> }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{ title: 'Portfolio', tabBarIcon: ({ color }) => <PieChart size={20} color={color} /> }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: 'Profile', tabBarIcon: ({ color }) => <User size={20} color={color} /> }}
      />
    </Tabs>
  );
}