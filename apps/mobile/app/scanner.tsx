import { colors, radii } from "@proofscan/design-tokens";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, Image, StyleSheet, Text, TextInput, View } from "react-native";
import { parseSellerLink, useSession } from "../src/session";
import { Action, Failure, Panel, Screen, styles } from "../src/ui";

export default function Scanner() {
  const router = useRouter();
  const client = useQueryClient();
  const seller = useSession(state => state.seller);
  const restored = useSession(state => state.restored);
  const restore = useSession(state => state.restore);
  const save = useSession(state => state.save);
  const clear = useSession(state => state.clear);
  const [text, setText] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<"open" | "forget" | null>(null);
  const busy = pending !== null;
  useEffect(() => {
    if (!restored) void restore().catch(() => setError(new Error("Couldn’t restore the saved session. You can open your original link again.")));
  }, [restore, restored]);

  async function openVerification() {
    if (!text.trim() || !restored || busy) return;
    setError(null);
    setPending("open");
    try {
      await save(parseSellerLink(text));
      client.removeQueries({ queryKey: ["mobile-seller"] });
      setText("");
      router.push("/seller");
    } catch (failure) {
      setError(failure);
    } finally {
      setPending(null);
    }
  }

  async function forgetSession() {
    setPending("forget");
    setError(null);
    try {
      await clear();
      client.removeQueries({ queryKey: ["mobile-seller"] });
    } catch {
      setError(new Error("Couldn’t remove the session from this phone. Try again."));
    } finally {
      setPending(null);
    }
  }

  return <Screen>
    <View style={scannerStyles.cover}>
      <Image accessible={false} source={require("../assets/icon.png")} style={scannerStyles.mark} />
      <Text accessibilityRole="header" style={[styles.title, scannerStyles.title]}>Verify this device</Text>
      <Text style={[styles.text, scannerStyles.description]}>Collect device readings, then choose what to share with your buyer.</Text>
    </View>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Open a seller link</Text>
      <Text style={styles.text}>Paste the complete link from your buyer.</Text>
      <TextInput style={styles.input} accessibilityLabel="Private seller link" value={text} onChangeText={setText}
        placeholder="Paste your private seller link" placeholderTextColor={colors.muted} autoComplete="off"
        importantForAutofill="no" autoCapitalize="none" autoCorrect={false} secureTextEntry editable={!busy}
        returnKeyType="go" onSubmitEditing={() => void openVerification()} />
      <Failure error={error} />
      <Action disabled={!text.trim() || !restored || busy} onPress={() => void openVerification()}>
        {pending === "open" ? "Opening verification…" : "Open verification"}
      </Action>
    </Panel>
    {seller && <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Saved session</Text>
      <Text style={styles.text}>Resume the verification you opened on this phone.</Text>
      <Action quiet disabled={busy} onPress={() => router.push("/seller")}>Resume verification</Action>
      <Action quiet disabled={busy} onPress={() => Alert.alert("Forget saved session?", "You’ll need the original link to open this verification again.", [
        { text: "Keep session", style: "cancel" },
        { text: "Forget session", style: "destructive", onPress: () => void forgetSession() },
      ])}>{pending === "forget" ? "Removing session…" : "Forget saved session"}</Action>
    </Panel>}
  </Screen>;
}

const scannerStyles = StyleSheet.create({
  cover: { padding: 20, gap: 8, backgroundColor: colors.navy, borderRadius: radii.cover },
  mark: { width: 44, height: 44, marginBottom: 6, borderRadius: radii.control },
  title: { color: colors.surface },
  description: { color: colors.surface, maxWidth: 420 },
});

