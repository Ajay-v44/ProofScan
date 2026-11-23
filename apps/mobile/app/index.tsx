import { colors } from "@proofscan/design-tokens";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { BackHandler, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";
import { apiOrigin } from "../src/session";
import { Action, Panel, Screen, styles } from "../src/ui";

type WorkspaceWebView = WebView<Record<never, never>>;

function configuredOrigin() {
  try { return apiOrigin(); }
  catch { return null; }
}

export default function Workspace() {
  const router = useRouter();
  const browser = useRef<WorkspaceWebView>(null);
  const canGoBack = useRef(false);
  const [attempt, setAttempt] = useState(0);
  const origin = configuredOrigin();

  useFocusEffect(useCallback(() => {
    const handle = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!canGoBack.current) return false;
      browser.current?.goBack();
      return true;
    });
    return () => handle.remove();
  }, []));

  function isWorkspaceUrl(value: string) {
    try {
      const url = new URL(value);
      return url.origin === origin && !url.username && !url.password;
    } catch { return false; }
  }

  if (!origin) return <Screen>
    <Text style={styles.title}>ProofScan</Text>
    <Panel><Text style={styles.heading}>Connect your workspace</Text>
      <Text style={styles.text}>Set EXPO_PUBLIC_PROOFSCAN_ORIGIN on your Expo host to open the ProofScan workspace here.</Text>
      <Action quiet onPress={() => router.push("/scanner")}>Open device scanner</Action>
    </Panel>
  </Screen>;

  return <SafeAreaView style={workspaceStyles.screen}>
    <View style={workspaceStyles.bar}>
      <Text style={workspaceStyles.label}>ProofScan</Text>
      <Pressable accessibilityRole="button" onPress={() => router.push("/scanner")} style={workspaceStyles.scanner}>
        <Text style={workspaceStyles.scannerText}>Device scanner</Text>
      </Pressable>
    </View>
    <WebView<Record<never, never>> ref={browser} key={attempt} source={{ uri: origin }} originWhitelist={["*"]} style={workspaceStyles.web}
      allowFileAccess={false} allowFileAccessFromFileURLs={false} allowUniversalAccessFromFileURLs={false}
      onShouldStartLoadWithRequest={request => isWorkspaceUrl(request.url)}
      onNavigationStateChange={state => { canGoBack.current = state.canGoBack; }}
      onOpenWindow={event => {
        const target = event.nativeEvent.targetUrl;
        if (isWorkspaceUrl(target)) browser.current?.injectJavaScript("location.assign(" + JSON.stringify(target) + "); true;");
      }}
      renderError={() => <Screen><Panel>
        <Text style={styles.heading}>Workspace unavailable</Text>
        <Text style={styles.text}>Check that your device can reach {origin}.</Text>
        <Action onPress={() => setAttempt(value => value + 1)}>Try again</Action>
      </Panel></Screen>}
    />
  </SafeAreaView>;
}

const workspaceStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface },
  bar: { height: 43, paddingLeft: 15, paddingRight: 8, flexDirection: "row", alignItems: "center",
    justifyContent: "space-between", borderBottomWidth: 1, borderBottomColor: colors.line },
  label: { color: colors.muted, fontWeight: "700", fontSize: 13 },
  scanner: { minHeight: 42, justifyContent: "center", paddingHorizontal: 9 },
  scannerText: { color: colors.brand, fontWeight: "700", fontSize: 13 },
  web: { flex: 1, backgroundColor: colors.canvas },
});
