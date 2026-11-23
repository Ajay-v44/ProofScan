import { useState } from "react";
import { Linking, Text, View } from "react-native";
import { parsePublicPage } from "../src/origin.cjs";
import { Action, Failure, Panel, Screen, styles } from "../src/ui";

const policyUrl = process.env.EXPO_PUBLIC_PROOFSCAN_PRIVACY_URL;
const deleteAccountUrl = process.env.EXPO_PUBLIC_PROOFSCAN_DELETE_ACCOUNT_URL;

export default function Privacy() {
  const [error, setError] = useState<unknown>(null);

  async function openPage(url: string | undefined, variable: string, failure: string) {
    setError(null);
    try {
      await Linking.openURL(parsePublicPage(url, variable));
    } catch {
      setError(new Error(failure + " Contact your workspace administrator."));
    }
  }

  return <Screen>
    <View style={styles.intro}>
      <Text accessibilityRole="header" style={styles.title}>Privacy in ProofScan</Text>
      <Text style={styles.text}>What the device scanner uses during a verification.</Text>
    </View>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Device readings</Text>
      <Text style={styles.text}>With your consent, the scanner sends the device manufacturer, model and available memory to your ProofScan workspace.</Text>
    </Panel>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Exterior photos</Text>
      <Text style={styles.text}>You can add photos of the device using your camera. The scanner uploads them to your workspace for review.</Text>
    </Panel>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Your report and link</Text>
      <Text style={styles.text}>You choose whether to share the signed report with the buyer. ProofScan stores your private seller session on this phone so you can resume it. You can forget the saved session from the device scanner.</Text>
    </Panel>
    <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Privacy policy</Text>
      {policyUrl
        ? <Action quiet onPress={() => void openPage(policyUrl, "EXPO_PUBLIC_PROOFSCAN_PRIVACY_URL", "Couldn’t open the privacy policy.")}>Open privacy policy</Action>
        : <Text style={styles.text}>Ask your workspace administrator for the privacy policy.</Text>}
    </Panel>
    {deleteAccountUrl && <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Account deletion</Text>
      <Text style={styles.text}>Manage deletion of your ProofScan account and associated data.</Text>
      <Action quiet onPress={() => void openPage(deleteAccountUrl, "EXPO_PUBLIC_PROOFSCAN_DELETE_ACCOUNT_URL", "Couldn’t open account deletion.")}>Open account deletion</Action>
    </Panel>}
    <Failure error={error} />
  </Screen>;
}
