import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Text, TextInput } from "react-native";
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
  useEffect(() => { if (!restored) void restore().catch(setError); }, [restore, restored]);
  return <Screen>
    <Text style={styles.title}>Device scanner</Text>
    <Panel>
      <Text style={styles.heading}>Open a seller link</Text>
      <Text style={styles.text}>Paste the private link your buyer sent you.</Text>
      <TextInput style={styles.input} accessibilityLabel="Private seller link" value={text} onChangeText={setText}
        autoCapitalize="none" autoCorrect={false} keyboardType="url" secureTextEntry />
      <Action disabled={!text.trim() || !restored} onPress={() => {
        setError(null);
        void (async () => {
          try { const parsed = parseSellerLink(text); await save(parsed); client.removeQueries({ queryKey: ["mobile-seller"] }); setText(""); router.push("/seller"); }
          catch (failure) { setError(failure); }
        })();
      }}>Open verification</Action>
      {seller && <><Action quiet onPress={() => router.push("/seller")}>Resume seller session</Action>
        <Action quiet onPress={() => void clear().then(() => client.removeQueries({ queryKey: ["mobile-seller"] })).catch(setError)}>Forget seller session</Action></>}
      <Failure error={error} />
    </Panel>
  </Screen>;
}

