import { colors, radii } from "@proofscan/design-tokens";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, BackHandler, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";
import { isWorkspaceUrl } from "../src/origin.cjs";
import { apiOrigin } from "../src/session";
import { Action, styles } from "../src/ui";

type WorkspaceWebView = WebView<Record<never, never>>;
type Connection = "loading" | "slow" | "ready" | "failed";

function configuredOrigin() {
  try { return apiOrigin(); }
  catch { return null; }
}

export default function Workspace() {
  const router = useRouter();
  const browser = useRef<WorkspaceWebView>(null);
  const canGoBack = useRef(false);
  const [connection, setConnection] = useState<Connection>("loading");
  const [attempt, setAttempt] = useState(0);
  const origin = configuredOrigin();
  const visible = !!origin && connection === "ready";
  const openScanner = () => router.push("/scanner");

  useEffect(() => {
    if (!origin || connection !== "loading") return;
    const timer = setTimeout(() => setConnection("slow"), 15_000);
    return () => clearTimeout(timer);
  }, [connection, origin, attempt]);

  useFocusEffect(useCallback(() => {
    const handle = BackHandler.addEventListener("hardwareBackPress", () => {
      if (!visible || !canGoBack.current) return false;
      browser.current?.goBack();
      return true;
    });
    return () => handle.remove();
  }, [visible]));

  function retry() {
    canGoBack.current = false;
    setConnection("loading");
    setAttempt(value => value + 1);
  }

  const startup = !origin
    ? { heading: "Workspace setup required", detail: "This build needs a ProofScan workspace address. Contact your workspace administrator." }
    : connection === "failed"
      ? { heading: "Can’t open the workspace", detail: "Check your connection and try again." }
      : connection === "slow"
        ? { heading: "Still connecting", detail: "If your connection is slow, give it a moment or try again." }
        : { heading: "Opening your workspace", detail: "Connecting to ProofScan securely." };

  return <SafeAreaView style={workspaceStyles.screen}>
    <View style={workspaceStyles.bar}>
      <Text accessibilityRole="header" style={workspaceStyles.label}>Device tools</Text>
      <View style={workspaceStyles.tools}>
        <Pressable accessibilityRole="button" onPress={() => router.push("/about")}
          style={({ pressed }) => [workspaceStyles.tool, pressed && workspaceStyles.pressed]}>
          <Text style={workspaceStyles.toolText}>About</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={openScanner}
          style={({ pressed }) => [workspaceStyles.tool, workspaceStyles.scanner, pressed && workspaceStyles.pressed]}>
          <Text style={workspaceStyles.toolText}>Scan device</Text>
        </Pressable>
      </View>
    </View>
    <View style={workspaceStyles.body}>
      {origin && <View pointerEvents={visible ? "auto" : "none"} accessibilityElementsHidden={!visible}
        importantForAccessibility={visible ? "auto" : "no-hide-descendants"} style={workspaceStyles.body}>
        <WebView<Record<never, never>> ref={browser} key={attempt} source={{ uri: origin + "/workspace" }} originWhitelist={["*"]} style={workspaceStyles.web}
          allowFileAccess={false} allowFileAccessFromFileURLs={false} allowUniversalAccessFromFileURLs={false}
          mixedContentMode="never" thirdPartyCookiesEnabled={false}
          onShouldStartLoadWithRequest={request => isWorkspaceUrl(request.url, origin)}
          onNavigationStateChange={state => { canGoBack.current = state.canGoBack; }}
          onOpenWindow={event => {
            const target = event.nativeEvent.targetUrl;
            if (isWorkspaceUrl(target, origin)) browser.current?.injectJavaScript("location.assign(" + JSON.stringify(target) + "); true;");
          }}
          onLoad={event => {
            if (isWorkspaceUrl(event.nativeEvent.url, origin)) {
              setConnection(value => value === "failed" ? value : "ready");
            }
          }}
          onHttpError={event => { if (event.nativeEvent.statusCode >= 500) setConnection("failed"); }}
          onError={() => setConnection("failed")}
          onContentProcessDidTerminate={() => setConnection("failed")}
          onRenderProcessGone={() => setConnection("failed")}
          renderError={() => <View />}
        />
      </View>}
      {!visible && <ScrollView style={workspaceStyles.overlay} contentContainerStyle={workspaceStyles.launch}
        keyboardShouldPersistTaps="handled">
        <View style={workspaceStyles.launchContent}>
          <Image accessible={false} source={require("../assets/icon.png")} style={workspaceStyles.mark} />
          <Text accessibilityRole="header" accessibilityLiveRegion="polite" style={styles.heading}>{startup.heading}</Text>
          <Text style={[styles.text, workspaceStyles.detail]}>{startup.detail}</Text>
          {!!origin && connection === "loading" && <ActivityIndicator color={colors.brand} />}
          {!!origin && connection !== "loading" && <Action onPress={retry}>Try again</Action>}
        </View>
      </ScrollView>}
    </View>
  </SafeAreaView>;
}

const workspaceStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface },
  bar: { minHeight: 54, paddingVertical: 3, paddingHorizontal: 14, gap: 6, flexDirection: "row", flexWrap: "wrap", alignItems: "center",
    justifyContent: "space-between", borderBottomWidth: 1, borderBottomColor: colors.line },
  label: { color: colors.ink, fontWeight: "800", fontSize: 16 },
  tools: { flexDirection: "row", flexWrap: "wrap", gap: 4 },
  tool: { minHeight: 48, justifyContent: "center", paddingHorizontal: 12, borderRadius: radii.control },
  scanner: { backgroundColor: colors.brandTint },
  toolText: { color: colors.brand, fontWeight: "700", fontSize: 14 },
  pressed: { opacity: 0.7 },
  body: { flex: 1, backgroundColor: colors.canvas },
  web: { flex: 1, backgroundColor: colors.canvas },
  overlay: { ...StyleSheet.absoluteFill, backgroundColor: colors.canvas },
  launch: { flexGrow: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  launchContent: { width: "100%", maxWidth: 320, alignItems: "center", gap: 15 },
  mark: { width: 72, height: 72, borderRadius: radii.cover, marginBottom: 5 },
  detail: { textAlign: "center" },
});
