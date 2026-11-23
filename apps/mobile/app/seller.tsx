import { api, type Angle, type GuestView, type ScanTicket } from "@proofscan/api-client";
import { colors } from "@proofscan/design-tokens";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Device from "expo-device";
import { fetch as expoFetch } from "expo/fetch";
import { File } from "expo-file-system";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Image, Platform, Text, View } from "react-native";
import { apiOrigin, useSession } from "../src/session";
import { Action, Failure, Panel, Screen, StepRail, styles } from "../src/ui";

const angles = ["front", "back", "left", "right"] as const;
const policy = "2026-11-23";

function clean(file: File | null) {
  try { if (file?.exists) file.delete(); } catch { /* Cache files are also cleared by the OS. */ }
}

export default function Seller() {
  const router = useRouter();
  const client = useQueryClient();
  const session = useSession(state => state.seller);
  const restored = useSession(state => state.restored);
  const restore = useSession(state => state.restore);
  const [restoreError, setRestoreError] = useState<unknown>(null);
  const [ticket, setTicket] = useState<ScanTicket | null>(null);
  const [angle, setAngle] = useState<Angle>("front");
  const platform = Platform.OS === "ios" ? "ios" : "android";
  const path = "/guest/" + session?.id;
  const key = ["mobile-seller", session?.id];

  useEffect(() => { if (!restored) void restore().catch(setRestoreError); }, [restore, restored]);

  function call<T>(suffix: string, data?: unknown) {
    if (!session) return Promise.reject(new Error("Open a private seller link first."));
    return api<T>(path + suffix, data, { origin: apiOrigin(), guestToken: session.guestToken });
  }

  const guest = useQuery({
    queryKey: key, enabled: !!session,
    queryFn: () => call<GuestView>("/exchange", { token: session?.guestToken }),
  });
  const save = (value: GuestView) => client.setQueryData(key, value);
  const consent = useMutation({
    mutationFn: () => call<GuestView>("/consent", { accepted: true, policy_version: policy }),
    onSuccess: save,
  });

  async function scanTicket() {
    if (ticket && Date.parse(ticket.expires_at) > Date.now() + 3000) return ticket;
    const fresh = await call<ScanTicket>("/scan", { platform });
    setTicket(fresh);
    return fresh;
  }

  const photo = useMutation({
    mutationFn: async () => {
      if (!session) throw new Error("Open a private seller link first.");
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) throw new Error("Allow camera access to capture a photo.");
      const current = await scanTicket();
      const captured = await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.8, exif: false });
      if (captured.canceled) return;
      const asset = captured.assets[0];
      const original = new File(asset.uri);
      let processed: File | null = null;
      try {
        const transform = ImageManipulator.manipulate(asset.uri);
        if (Math.max(asset.width, asset.height) > 1280) {
          transform.resize(asset.width >= asset.height ? { width: 1280 } : { height: 1280 });
        }
        const image = await transform.renderAsync();
        const saved = await image.saveAsync({ format: SaveFormat.JPEG, compress: 0.76 });
        processed = new File(saved.uri);
        if (processed.size > 750_000) throw new Error("Try a clearer photo with a plain background.");
        const response = await expoFetch(apiOrigin() + "/api/v1" + path + "/photos?angle=" + angle, {
          method: "POST",
          headers: { "Content-Type": "image/jpeg", "X-Guest-Token": session.guestToken, "X-Scan-Challenge": current.challenge },
          body: await processed.arrayBuffer(),
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail ?? "The photo could not be saved.");
        }
      } finally { clean(processed); clean(original); }
    },
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });

  const submit = useMutation({
    mutationFn: async () => {
      if (!Device.isDevice) throw new Error("Open ProofScan on the device you are selling.");
      const scan = await scanTicket();
      const model = Device.modelName?.trim().slice(0, 120) || null;
      const manufacturer = Device.manufacturer?.trim().slice(0, 120) || null;
      const memory = Device.totalMemory ? Math.max(1, Math.round(Device.totalMemory / 2 ** 30)) : null;
      if (!model && !memory) throw new Error("This device did not disclose supported hardware readings.");
      return call<GuestView>("/submit", {
        scan_id: scan.scan_id, challenge: scan.challenge, platform,
        hardware: { manufacturer, model, memory_gib: memory, cpu: [], gpu: [], drives: [] },
      });
    },
    onSuccess: save,
  });
  const decision = useMutation({
    mutationFn: (value: "share" | "decline") => call<GuestView>("/decision", { decision: value }),
    onSuccess: save,
  });
  const status = guest.data?.verification.status;
  const step = status === "COMPLETED" || status === "DECLINED" ? 3 : status === "SELLER_REVIEW" ? 2
    : status === "CONSENTED" || status === "SCANNING" ? 1 : 0;
  const preview = guest.data?.preview;
  const busy = consent.isPending || photo.isPending || submit.isPending || decision.isPending;

  return <Screen>
    <Text style={styles.title}>{guest.data?.verification.label ?? "Seller verification"}</Text>
    {status && <StepRail steps={["Consent", "Collect", "Review", "Decision"]} current={step} />}
    <Failure error={restoreError ?? guest.error ?? consent.error ?? photo.error ?? submit.error ?? decision.error} />
    {!restored || (session && guest.isPending) ? <Text style={styles.text}>Opening seller session…</Text> : null}
    {restored && !session && <Action onPress={() => router.replace("/scanner")}>Open a seller link</Action>}
    {status === "SELLER_OPENED" && <Panel>
      <Text style={styles.heading}>Review what we collect</Text>
      <Text style={styles.text}>ProofScan reads device model and memory where available. You can add exterior photos, then review everything before the buyer sees it.</Text>
      <Action disabled={busy} onPress={() => consent.mutate()}>Agree and continue</Action>
    </Panel>}
    {(status === "CONSENTED" || status === "SCANNING") && <Panel>
      <Text style={styles.heading}>Collect device readings</Text>
      <Text style={styles.text}>Battery health and physical drive capacity are unavailable in this mobile collector.</Text>
      <Text style={styles.heading}>Optional exterior photos</Text>
      <Text style={styles.text}>Choose a side and photograph the entire device in even light.</Text>
      <View style={{ gap: 7 }}>{angles.map(item => <Action key={item} quiet={item !== angle} disabled={busy} onPress={() => setAngle(item)}>{item}</Action>)}</View>
      <Action quiet disabled={busy} onPress={() => photo.mutate()}>{photo.isPending ? "Checking photo…" : "Take photo"}</Action>
      {!!guest.data?.photos.length && <Text style={styles.text}>Saved views {guest.data.photos.map(item => item.angle).join(", ")}</Text>}
      <Action disabled={busy} onPress={() => submit.mutate()}>{submit.isPending ? "Collecting…" : "Collect and preview"}</Action>
    </Panel>}
    {status === "SELLER_REVIEW" && preview && <Panel>
      <Text style={styles.heading}>Review before sharing</Text>
      <Text style={styles.text}>{[preview.hardware.manufacturer, preview.hardware.model].filter(Boolean).join(" ") || "Model unavailable"}</Text>
      <Text style={styles.text}>{preview.hardware.memory_gib ? preview.hardware.memory_gib + " GiB memory" : "Memory unavailable"}</Text>
      {preview.findings.map(item => <Text key={item.metric} style={styles.text}>
        {item.metric} · {item.observed ?? "Unavailable"} · {item.status.toLowerCase()}
      </Text>)}
      {!!preview.visual_evidence?.length && session && <Text style={styles.heading}>Exterior photos</Text>}
      {preview.visual_evidence?.map(item => session ? <Image key={item.id} accessibilityLabel={item.angle + " of device"}
        style={{ height: 185, width: "100%", backgroundColor: colors.canvas }} resizeMode="contain"
        source={{ uri: apiOrigin() + "/api/v1" + path + "/photos/" + item.id, headers: { "X-Guest-Token": session.guestToken } }} /> : null)}
      <Action disabled={busy} onPress={() => decision.mutate("share")}>Share signed report</Action>
      <Action quiet disabled={busy} onPress={() => decision.mutate("decline")}>Decline to share</Action>
    </Panel>}
    {status === "COMPLETED" && <Panel><Text style={styles.heading}>Report shared</Text><Text style={styles.text}>The buyer can open the signed report in their workspace.</Text></Panel>}
    {status === "DECLINED" && <Panel><Text style={styles.heading}>Sharing declined</Text><Text style={styles.text}>Your readings stayed private.</Text></Panel>}
  </Screen>;
}
