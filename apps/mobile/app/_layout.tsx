import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useState } from "react";

export default function Layout() {
  const [query] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  return <QueryClientProvider client={query}><StatusBar style="dark" />
    <Stack screenOptions={{ headerTintColor: colors.brand, headerStyle: { backgroundColor: colors.surface } }}>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="scanner" options={{ title: "Device scanner" }} />
      <Stack.Screen name="seller" options={{ title: "Seller verification" }} />
    </Stack>
  </QueryClientProvider>;
}
import { colors } from "@proofscan/design-tokens";
