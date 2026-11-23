import "react-native-url-polyfill/auto";
import { colors } from "@proofscan/design-tokens";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack, type ErrorBoundaryProps } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useState } from "react";
import { Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Action, Panel, styles } from "../src/ui";

export function ErrorBoundary({ retry }: ErrorBoundaryProps) {
  return <SafeAreaView style={styles.screen}>
    <Panel style={{ margin: 18 }}>
      <Text accessibilityRole="header" style={styles.heading}>ProofScan couldn’t open this screen</Text>
      <Text style={styles.text}>Try opening the screen again.</Text>
      <Action onPress={() => void retry()}>Try again</Action>
    </Panel>
  </SafeAreaView>;
}

export default function Layout() {
  const [query] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  return <QueryClientProvider client={query}><StatusBar style="dark" />
    <Stack screenOptions={{
      contentStyle: { backgroundColor: colors.canvas },
      headerTintColor: colors.brand,
      headerStyle: { backgroundColor: colors.surface },
      headerShadowVisible: false,
    }}>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="scanner" options={{ title: "Device scanner" }} />
      <Stack.Screen name="seller" options={{ title: "Seller verification" }} />
      <Stack.Screen name="privacy" options={{ title: "Privacy" }} />
    </Stack>
  </QueryClientProvider>;
}
