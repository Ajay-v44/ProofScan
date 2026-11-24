import { radii } from "@proofscan/design-tokens";
import Constants from "expo-constants";
import { useRouter } from "expo-router";
import { Image, StyleSheet, Text, View } from "react-native";
import { Action, Panel, Screen, styles } from "../src/ui";

export default function About() {
  const router = useRouter();
  const version = Constants.expoConfig?.version;

  return <Screen>
    <View style={aboutStyles.identity}>
      <Image accessible={false} source={require("../assets/icon.png")} style={aboutStyles.mark} />
      <View style={aboutStyles.identityText}>
        <Text accessibilityRole="header" style={styles.title}>ProofScan</Text>
        {version && <Text style={styles.text}>App version {version}</Text>}
      </View>
    </View>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Check a device</Text>
      <Text style={styles.text}>Collect available readings and take exterior photos before sharing a purchase report. Compare the evidence again when you have the device in hand.</Text>
      <Action quiet onPress={() => router.push("/scanner")}>Open the device scanner</Action>
    </Panel>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Privacy and account</Text>
      <Text style={styles.text}>See what the scanner collects and how to manage your saved session and account.</Text>
      <Action quiet onPress={() => router.push("/privacy")}>Open privacy information</Action>
    </Panel>
  </Screen>;
}

const aboutStyles = StyleSheet.create({
  identity: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 14, paddingVertical: 8 },
  mark: { width: 60, height: 60, borderRadius: radii.card },
  identityText: { flexShrink: 1, gap: 2 },
});
