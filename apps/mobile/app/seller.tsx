import { api, ApiError, type Angle, type CaptureLink, type DevicePlan, type GuestView, type ScanTicket } from "@proofscan/api-client";
import { colors, radii } from "@proofscan/design-tokens";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Device from "expo-device";
import { fetch as expoFetch } from "expo/fetch";
import { File } from "expo-file-system";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Image, Linking, Platform, Pressable, Share, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { runDeviceTool, type MobileReadings } from "../src/device-tools";
import { apiOrigin, useSession } from "../src/session";
import { Action, Failure, Panel, Screen, StepRail, styles } from "../src/ui";

const angles = ["front", "back", "left", "right"] as const;
const angleLabel: Record<Angle, string> = { front: "Front", back: "Back", left: "Left side", right: "Right side" };
const steps = ["Consent", "Collect", "Review", "Decision"];
const policy = "2026-11-23";

function clean(file: File | null) {
  try { if (file?.exists) file.delete(); } catch { /* Cache files are also cleared by the OS. */ }
}

function sellerFetch(url: string, init: Parameters<typeof expoFetch>[1]) {
  return expoFetch(url, { ...init, credentials: "omit", redirect: "error", signal: init?.signal ?? AbortSignal.timeout(30_000) });
}

function ReviewPhoto({ uri, angle, token, paired }: { uri: string; angle: Angle; token: string; paired: boolean }) {
  const [failed, setFailed] = useState(false);
  return <View style={[sellerStyles.photoCard, paired && sellerStyles.photoPaired]}>
    {failed ? <Text style={styles.text}>Photo unavailable</Text> : <Image
      accessibilityLabel={angleLabel[angle] + " of device"} style={sellerStyles.evidence} resizeMode="contain"
      onError={() => setFailed(true)} source={{ uri, headers: { "X-Guest-Token": token } }} />}
    <Text style={styles.fieldLabel}>{angleLabel[angle]}</Text>
  </View>;
}

export default function Seller() {
  const { width, fontScale } = useWindowDimensions();
  const router = useRouter();
  const client = useQueryClient();
  const session = useSession(state => state.seller);
  const restored = useSession(state => state.restored);
  const restore = useSession(state => state.restore);
  const [restoreError, setRestoreError] = useState<unknown>(null);
  const [ticket, setTicket] = useState<ScanTicket | null>(null);
  const [angle, setAngle] = useState<Angle>("front");
  const [cameraSettingsNeeded, setCameraSettingsNeeded] = useState(false);
  const [cameraSettingsError, setCameraSettingsError] = useState<unknown>(null);
  const [localCamera, setLocalCamera] = useState(false);
  const [plan, setPlan] = useState<DevicePlan | null>(null);
  const platform = Platform.OS === "ios" ? "ios" : "android";
  const path = "/guest/" + session?.id;
  const key = ["mobile-seller", session?.id];

  useEffect(() => {
    if (!restored) void restore().catch(() => setRestoreError(new Error("Couldn’t restore your session. Open the original seller link again.")));
  }, [restore, restored]);

  function call<T>(suffix: string, data?: unknown) {
    if (!session) return Promise.reject(new Error("Open a private seller link first."));
    return api<T>(path + suffix, data, { origin: apiOrigin(), guestToken: session.guestToken, fetcher: sellerFetch });
  }

  const guest = useQuery({
    queryKey: key, enabled: !!session,
    queryFn: async () => {
      const current = await call<GuestView>("");
      return current.verification.status === "LINK_CREATED"
        ? call<GuestView>("/exchange", { token: session?.guestToken }) : current;
    },
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

  const cameraLink = useMutation({
    mutationFn: async () => {
      await scanTicket();
      const link = await call<CaptureLink>("/photo-link", {});
      await Share.share({ message: link.url });
    },
    onSettled: () => guest.refetch(),
  });

  const photo = useMutation({
    mutationFn: async () => {
      if (!session) throw new Error("Open a private seller link first.");
      setCameraSettingsError(null);
      let permission = await ImagePicker.getCameraPermissionsAsync();
      if (!permission.granted && permission.canAskAgain) permission = await ImagePicker.requestCameraPermissionsAsync();
      setCameraSettingsNeeded(!permission.granted && !permission.canAskAgain);
      if (!permission.granted) throw new Error("Allow camera access to take an exterior photo.");
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
        const current = await scanTicket();
        const response = await sellerFetch(apiOrigin() + "/api/v1" + path + "/photos?angle=" + angle, {
          method: "POST",
          headers: { "Content-Type": "image/jpeg", "X-Guest-Token": session.guestToken, "X-Scan-Challenge": current.challenge },
          body: await processed.arrayBuffer(),
        }).catch(() => { throw new Error("Couldn’t upload the photo. Check your connection and try again."); });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail ?? "The photo could not be saved.");
        }
        return angle;
      } finally { clean(processed); clean(original); }
    },
    onSuccess: captured => {
      if (!captured) return;
      const next = angles.find(view => view !== captured && !guest.data?.photos.some(saved => saved.angle === view));
      if (next) setAngle(next);
    },
    onSettled: () => client.invalidateQueries({ queryKey: key }),
  });

  async function submitReadings(readings: MobileReadings) {
    if (!readings.model && !readings.memory_gib) throw new Error("This device did not disclose supported hardware readings.");
    const scan = await scanTicket();
    return call<GuestView>("/submit", {
      scan_id: scan.scan_id, challenge: scan.challenge, platform,
      hardware: { ...readings, cpu: [], gpu: [], drives: [] },
    });
  }

  const prepare = useMutation({
    mutationFn: async () => {
      if (!Device.isDevice) throw new Error("Open ProofScan on the device you are selling.");
      await scanTicket();
      return call<DevicePlan>("/agent/plan", { platform });
    },
    onSuccess: setPlan,
  });
  const skipPlan = useMutation({
    mutationFn: (current: DevicePlan) => call<DevicePlan>("/agent/plan/" + current.id, {
      revision: current.revision, action: "skip",
    }),
    onSuccess: () => setPlan(null),
  });
  const submit = useMutation({
    mutationFn: async (approvedPlan: DevicePlan | null) => {
      if (!Device.isDevice) throw new Error("Open ProofScan on the device you are selling.");
      if (!approvedPlan) return submitReadings({
        ...runDeviceTool("model_name").readings,
        ...runDeviceTool("memory_total").readings,
      });
      const planPath = "/agent/plan/" + approvedPlan.id;
      let next = await call<DevicePlan>(planPath, { revision: approvedPlan.revision, action: "approve" });
      const readings: MobileReadings = {};
      for (let count = 0; count < 3 && next.status === "collecting"; count++) {
        if (!next.next_tool) throw new Error("ProofScan did not receive the next device check.");
        const result = runDeviceTool(next.next_tool);
        Object.assign(readings, result.readings);
        next = await call<DevicePlan>(planPath, {
          revision: next.revision, action: "observe", tool: next.next_tool, outcome: result.outcome,
        });
      }
      if (next.status !== "complete") throw new Error("The guided scan did not finish. Start a new plan or use basic collection.");
      return submitReadings(readings);
    },
    onSuccess: save,
    onSettled: () => setPlan(null),
    onError: () => { setTicket(null); void guest.refetch(); },
  });
  const decision = useMutation({
    mutationFn: (value: "share" | "decline") => call<GuestView>("/decision", { decision: value }),
    onSuccess: save,
    onError: () => { void guest.refetch(); },
  });
  const status = guest.data?.verification.status;
  const step = status === "COMPLETED" || status === "DECLINED" ? 3 : status === "SELLER_REVIEW" ? 2
    : status === "CONSENTED" || status === "SCANNING" ? 1 : 0;
  const preview = guest.data?.preview;
  const busy = consent.isPending || photo.isPending || cameraLink.isPending || submit.isPending || decision.isPending ||
    prepare.isPending || skipPlan.isPending;
  const collecting = status === "CONSENTED" || status === "SCANNING";
  const linkUnavailable = guest.error instanceof ApiError && guest.error.status === 404;
  const savedAngles = new Set(guest.data?.photos.map(item => item.angle));
  const requiresPhotos = guest.data?.verification.require_exterior === true;
  const missingPhotos = requiresPhotos && (!savedAngles.has("front") || !savedAngles.has("back"));
  const stageError = status === "SELLER_OPENED" ? consent.error
    : collecting ? submit.error ?? prepare.error ?? skipPlan.error
      : status === "SELLER_REVIEW" ? decision.error : null;

  return <Screen>
    <View style={styles.intro}>
      <Text accessibilityRole="header" style={styles.title}>{guest.data?.verification.label ?? "Your verification"}</Text>
      <Text style={styles.text}>{guest.data?.verification.is_pickup ? "Capture fresh evidence from the device in your hands." : "Review your readings and photos before sharing a report."}</Text>
    </View>
    {status && !linkUnavailable && <StepRail steps={steps} current={step} />}
    <Failure error={restoreError ?? guest.error ?? stageError} />
    {(!restored || (session && guest.isPending && guest.isFetching)) && <Panel style={sellerStyles.loading}>
      <ActivityIndicator color={colors.brand} />
      <Text accessibilityLiveRegion="polite" style={styles.text}>Opening seller session…</Text>
    </Panel>}
    {guest.isError && !linkUnavailable && <Action quiet disabled={guest.isFetching} onPress={() => void guest.refetch()}>Reconnect</Action>}
    {restored && (!session || linkUnavailable) && <Action onPress={() => router.replace("/scanner")}>Open a seller link</Action>}
    {linkUnavailable && <Text style={styles.text}>Ask your buyer for a fresh seller link.</Text>}
    {!linkUnavailable && <>
    {status === "SELLER_OPENED" && <Panel>
      <Text style={styles.heading}>Review what we collect</Text>
      <Text style={styles.text}>ProofScan reads device model and memory where available. {requiresPhotos ? "Take front and back photos, then review everything before sharing." : "You can add exterior photos before reviewing."}</Text>
      <Action disabled={busy} onPress={() => consent.mutate()}>{consent.isPending ? "Saving consent…" : "Agree and continue"}</Action>
    </Panel>}
    {collecting && <>
      <Panel>
        <Text accessibilityRole="header" style={styles.heading}>Exterior photos</Text>
        <Text style={styles.text}>{requiresPhotos ? "Use another phone or tablet to photograph the front and back of this device." : "Use a second device to photograph this device."} Keep faces and serial labels out of frame.</Text>
        <View accessibilityRole="radiogroup" style={sellerStyles.angleGroup}>
          {angles.map(item => {
            const selected = item === angle;
            return <Pressable key={item} accessibilityRole="radio" accessibilityState={{ checked: selected, disabled: busy }}
              disabled={busy} onPress={() => setAngle(item)}
              style={({ pressed }) => [sellerStyles.angle, selected && sellerStyles.angleSelected, pressed && sellerStyles.anglePressed]}>
              <Text style={[styles.fieldLabel, selected && sellerStyles.selectedLabel]}>{angleLabel[item]}</Text>
              {savedAngles.has(item) && <Text style={sellerStyles.saved}>Saved</Text>}
            </Pressable>;
          })}
        </View>
        <Action disabled={busy} onPress={() => cameraLink.mutate()}>{cameraLink.isPending ? "Opening share options…" : "Share camera link"}</Action>
        <Text style={styles.text}>The link lasts up to 15 minutes. Refresh after the photos are saved.</Text>
        <Action quiet disabled={busy || guest.isFetching} onPress={() => void guest.refetch()}>{guest.isFetching ? "Refreshing…" : "Refresh photos"}</Action>
        <Failure error={cameraLink.error} />
        <Action quiet disabled={busy} onPress={() => setLocalCamera(value => !value)}>{localCamera ? "Hide this camera" : "Use this camera"}</Action>
        {localCamera && <Action quiet disabled={busy} onPress={() => { submit.reset(); photo.mutate(); }}>
          {photo.isPending ? "Saving photo…" : savedAngles.has(angle) ? "Retake photo" : "Take photo"}
        </Action>}
        <Failure error={photo.error ?? cameraSettingsError} />
        {cameraSettingsNeeded && <Action quiet onPress={() => void Linking.openSettings().catch(() => {
          setCameraSettingsError(new Error("Open your phone’s settings and allow camera access for ProofScan."));
        })}>Open camera settings</Action>}
      </Panel>
      <Panel>
        <Text accessibilityRole="header" style={styles.heading}>Device readings</Text>
        <Text style={styles.text}>ProofScan reads the model and memory when available.</Text>
        {plan ? <>
          <Text style={styles.text}>Approve local model and memory checks. If the model name is unavailable, ProofScan may try the operating system’s model code. The planner may send check names and outcomes to Moonshot. You review the actual readings before sharing.</Text>
          <Action disabled={busy || missingPhotos} onPress={() => { photo.reset(); submit.mutate(plan); }}>
            {submit.isPending ? "Collecting…" : "Approve checks and collect"}
          </Action>
          <Action quiet disabled={busy} onPress={() => skipPlan.mutate(plan)}>Skip guided checks</Action>
        </> : <>
          <Action disabled={busy || missingPhotos} onPress={() => { submit.reset(); prepare.mutate(); }}>
            {prepare.isPending ? "Preparing checks…" : "Plan guided scan"}
          </Action>
          <Action quiet disabled={busy || missingPhotos} onPress={() => { photo.reset(); prepare.reset(); skipPlan.reset(); submit.mutate(null); }}>
            {submit.isPending ? "Collecting…" : "Use basic collection"}
          </Action>
        </>}
        {missingPhotos && <Text style={styles.text}>Save front and back photos before collecting readings.</Text>}
      </Panel>
    </>}
    {status === "SELLER_REVIEW" && preview && <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Review before sharing</Text>
      <View style={sellerStyles.readings}>{[
        ["Reported device", [preview.hardware.manufacturer, preview.hardware.model].filter(Boolean).join(" ") || "Unavailable"],
        ["Memory", preview.hardware.memory_gib ? preview.hardware.memory_gib + " GiB" : "Unavailable"],
      ].map(([label, value]) => <View key={label} style={sellerStyles.reading}>
        <Text style={styles.fieldLabel}>{label}</Text><Text style={styles.text}>{value}</Text>
      </View>)}</View>
      {!!preview.findings.length && <>
        <Text accessibilityRole="header" style={styles.heading}>Listing comparison</Text>
        {preview.findings.map(item => <View key={item.metric} style={sellerStyles.finding}>
          <Text style={styles.fieldLabel}>{item.metric}</Text>
          <Text style={styles.text}>Claimed {item.claimed} · Observed {item.observed ?? "unavailable"}</Text>
          <Text style={[styles.fieldLabel, item.status === "MISMATCH" ? sellerStyles.difference : item.status === "MATCH" ? sellerStyles.match : null]}>
            {item.status === "MATCH" ? "Matches listing" : item.status === "MISMATCH" ? "Differs from listing" : "Check unavailable"}
          </Text>
        </View>)}
      </>}
      {!!preview.visual_evidence?.length && session && <>
        <Text accessibilityRole="header" style={styles.heading}>Exterior photos</Text>
        <View style={sellerStyles.angleGroup}>{preview.visual_evidence.map(item => <ReviewPhoto key={item.id} angle={item.angle}
          uri={apiOrigin() + "/api/v1" + path + "/photos/" + item.id} token={session.guestToken}
          paired={width >= 360 && fontScale <= 1.3} />)}</View>
      </>}
      <Action disabled={busy} onPress={() => decision.mutate("share")}>{decision.isPending ? "Saving decision…" : "Share signed report"}</Action>
      <Action quiet disabled={busy} onPress={() => decision.mutate("decline")}>Decline to share</Action>
    </Panel>}
    {status === "COMPLETED" && <Panel><Text style={styles.heading}>Report shared</Text><Text style={styles.text}>The buyer can open the signed report in their workspace.</Text></Panel>}
    {status === "DECLINED" && <Panel><Text style={styles.heading}>Sharing declined</Text><Text style={styles.text}>Your readings stayed private.</Text></Panel>}
    {(status === "EXPIRED" || status === "CANCELLED" || status === "FAILED") && <Panel>
      <Text accessibilityRole="header" style={styles.heading}>Verification unavailable</Text>
      <Text style={styles.text}>Ask your buyer for a fresh seller link.</Text>
      <Action quiet onPress={() => router.replace("/scanner")}>Back to device scanner</Action>
    </Panel>}
    </>}
  </Screen>;
}

const sellerStyles = StyleSheet.create({
  loading: { flexDirection: "row", alignItems: "center" },
  angleGroup: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  angle: { flexBasis: "46%", flexGrow: 1, minHeight: 48, justifyContent: "center", padding: 11, borderWidth: 1,
    borderColor: colors.border, borderRadius: radii.control },
  angleSelected: { borderColor: colors.focus, backgroundColor: colors.brandTint },
  selectedLabel: { color: colors.brand },
  anglePressed: { opacity: 0.7 },
  saved: { alignSelf: "flex-start", marginTop: 4, color: colors.mintInk, fontSize: 13, fontWeight: "700" },
  readings: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  reading: { flexBasis: 128, flexGrow: 1, gap: 3, padding: 10, backgroundColor: colors.canvas, borderRadius: radii.control },
  finding: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 10, gap: 3 },
  match: { color: colors.mintInk },
  difference: { color: colors.creamInk },
  photoCard: { flexBasis: "100%", flexGrow: 1, minWidth: 0, gap: 6, padding: 8, borderWidth: 1, borderColor: colors.line, borderRadius: radii.control },
  photoPaired: { flexBasis: "46%" },
  evidence: { aspectRatio: 4 / 3, width: "100%", borderRadius: radii.control, backgroundColor: colors.canvas },
});
