import { colors } from "@proofscan/design-tokens";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, Text, TextInput, View } from "react-native";
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
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!restored) void restore().catch(() => setError(new Error("Couldn’t restore the saved session. You can open your original link again.")));
  }, [restore, restored]);

  async function openVerification() {
    if (!text.trim() || !restored || busy) return;
    setError(null);
    setBusy(true);
    try {
      await save(parseSellerLink(text));
      client.removeQueries({ queryKey: ["mobile-seller"] });
      setText("");
      router.push("/seller");
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  async function forgetSession() {
    setBusy(true);
    setError(null);
    try {
      await clear();
      client.removeQueries({ queryKey: ["mobile-seller"] });
    } catch {
      setError(new Error("Couldn’t remove the session from this phone. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return <Screen>
    <View style={styles.intro}>
      <Text accessibilityRole="header" style={styles.title}>Verify this device</Text>
      <Text style={styles.text}>Collect device readings, then choose what to share with your buyer.</Text>
    </View>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Open a seller link</Text>
      <Text style={styles.text}>Paste the complete link from your buyer.</Text>
      <TextInput style={styles.input} accessibilityLabel="Private seller link" value={text} onChangeText={setText}
        placeholder="Paste your private seller link" placeholderTextColor={colors.muted} autoComplete="off"
        importantForAutofill="no" autoCapitalize="none" autoCorrect={false} secureTextEntry editable={!busy}
        returnKeyType="go" onSubmitEditing={() => void openVerification()} />
      <Failure error={error} />
      <Action disabled={!text.trim() || !restored || busy} onPress={() => void openVerification()}>Open verification</Action>
    </Panel>
    {seller && <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Saved session</Text>
      <Text style={styles.text}>Resume the verification you opened on this phone.</Text>
      <Action quiet disabled={busy} onPress={() => router.push("/seller")}>Resume verification</Action>
      <Action quiet disabled={busy} onPress={() => Alert.alert("Forget saved session?", "You’ll need the original link to open this verification again.", [
        { text: "Keep session", style: "cancel" },
        { text: "Forget session", style: "destructive", onPress: () => void forgetSession() },
      ])}>Forget saved session</Action>
    </Panel>}
  </Screen>;
}

