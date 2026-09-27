/**
 * Product icon set — Phosphor (SSR build).
 *
 * Every component imports icons from this module instead of an icon package
 * directly. Each export keeps the name the component already used, so no call
 * site changes when the icon set is swapped or re-skinned.
 *
 * The `/ssr` entry point is required: Phosphor's main entry uses React context,
 * which throws inside a Server Component. This build is context-free and is
 * safe in both server and client components.
 */
import type { Icon, IconProps } from "@phosphor-icons/react/dist/lib/types";
import {
  Archive as PhArchive,
  ArrowCounterClockwise as PhArrowCounterClockwise,
  ArrowRight as PhArrowRight,
  ArrowSquareOut as PhArrowSquareOut,
  ArrowUp as PhArrowUp,
  ArrowUpRight as PhArrowUpRight,
  BookOpen as PhBookOpen,
  Bookmark as PhBookmark,
  BracketsCurly as PhBracketsCurly,
  Brain as PhBrain,
  Briefcase as PhBriefcase,
  Broadcast as PhBroadcast,
  Bug as PhBug,
  CalendarBlank as PhCalendarBlank,
  CalendarPlus as PhCalendarPlus,
  CaretRight as PhCaretRight,
  ChartBar as PhChartBar,
  ChatCircle as PhChatCircle,
  Check as PhCheck,
  CheckCircle as PhCheckCircle,
  Circle as PhCircle,
  Clock as PhClock,
  ClockCounterClockwise as PhClockCounterClockwise,
  Code as PhCode,
  Database as PhDatabase,
  EyeSlash as PhEyeSlash,
  FileCode as PhFileCode,
  Fingerprint as PhFingerprint,
  FlowArrow as PhFlowArrow,
  Funnel as PhFunnel,
  Folder as PhFolder,
  Gear as PhGear,
  GearSix as PhGearSix,
  GitBranch as PhGitBranch,
  Globe as PhGlobe,
  Info as PhInfo,
  Layout as PhLayout,
  Lightning as PhLightning,
  List as PhList,  ListChecks as PhListChecks,
  LockKey as PhLockKey,
  MagnifyingGlass as PhMagnifyingGlass,
  MapPin as PhMapPin,
  Microphone as PhMicrophone,
  Monitor as PhMonitor,
  Moon as PhMoon,
  Notebook as PhNotebook,
  Note as PhNote,
  Paperclip as PhPaperclip,
  PaperPlaneTilt as PhPaperPlaneTilt,
  Plugs as PhPlugs,
  Play as PhPlay,
  Plus as PhPlus,
  Power as PhPower,
  Prohibit as PhProhibit,
  Pulse as PhPulse,
  Rocket as PhRocket,
  Shapes as PhShapes,
  ShieldCheck as PhShieldCheck,
  ShieldWarning as PhShieldWarning,
  SlidersHorizontal as PhSlidersHorizontal,
  Sparkle as PhSparkle,
  SpinnerGap as PhSpinnerGap,
  Star as PhStar,
  Sun as PhSun,
  Timer as PhTimer,
  Trash as PhTrash,
  Tray as PhTray,
  UserCircle as PhUserCircle,
  Users as PhUsers,
  Warning as PhWarning,
  WarningCircle as PhWarningCircle,
  Waveform as PhWaveform,
  X as PhX,
} from "@phosphor-icons/react/ssr";

export type ProductIconProps = IconProps;
/** Icon component type used by the props that accept an icon. */
export type ProductIcon = Icon;

export const Activity = PhPulse;
export const AlertCircle = PhInfo;
export const AlertTriangle = PhWarning;
export const Archive = PhArchive;
export const ArrowRight = PhArrowRight;
export const ArrowUpRight = PhArrowUpRight;
export const BarChart3 = PhChartBar;
export const Bookmark = PhBookmark;
export const BookOpenText = PhBookOpen;
export const Bot = PhWaveform;
export const Braces = PhBracketsCurly;
export const Brain = PhBrain;
export const Memory = PhNotebook;
export const Motor = PhBrain;
export const MotorCircuit = PhBrain;
export const Wave = PhWaveform;
/** Kept for call sites that predate the Brain / Memory icon split. */
export const BrainCircuit = PhBrain;
export const BriefcaseBusiness = PhBriefcase;
export const Bug = PhBug;
export const Cable = PhPlugs;
export const CalendarClock = PhCalendarBlank;
export const CalendarDays = PhCalendarBlank;
export const CalendarPlus = PhCalendarPlus;
export const Check = PhCheck;
export const CheckCheck = PhCheckCircle;
export const CheckCircle2 = PhCheckCircle;
export const ChevronRight = PhCaretRight;
export const CircleAlert = PhWarningCircle;
export const CircleDot = PhCircle;
export const CircleOff = PhProhibit;
export const Clock3 = PhClock;
export const Code2 = PhCode;
export const DatabaseZap = PhDatabase;
export const ExternalLink = PhArrowSquareOut;
export const EyeOff = PhEyeSlash;
export const FileCode2 = PhFileCode;
export const Filter = PhFunnel;
export const Fingerprint = PhFingerprint;
export const GitBranch = PhGitBranch;
export const Globe2 = PhGlobe;
export const History = PhClockCounterClockwise;
export const Inbox = PhTray;
export const LayoutDashboard = PhLayout;
export const ListTodo = PhListChecks;
export const LoaderCircle = PhSpinnerGap;
export const LockKeyhole = PhLockKey;
export const MapPin = PhMapPin;
export const Menu = PhList;
export const MessageCircle = PhChatCircle;
export const MonitorSmartphone = PhMonitor;
export const Play = PhPlay;
export const PlugZap = PhPlugs;
export const Plus = PhPlus;
export const Power = PhPower;
export const RadioTower = PhBroadcast;
export const Rocket = PhRocket;
export const RotateCcw = PhArrowCounterClockwise;
export const Save = PhNote;
export const Search = PhMagnifyingGlass;
export const Send = PhPaperPlaneTilt;
export const Settings = PhGear;
export const Settings2 = PhGearSix;
export const Shapes = PhShapes;
export const ShieldCheck = PhShieldCheck;
export const ShieldQuestion = PhShieldWarning;
export const SlidersHorizontal = PhSlidersHorizontal;
export const Sparkles = PhSparkle;
export const Timer = PhTimer;
export const Trash2 = PhTrash;
export const UserRound = PhUserCircle;
export const Users = PhUsers;
export const Workflow = PhFlowArrow;
export const X = PhX;
export const Zap = PhLightning;

/* Native Phosphor names, for code that prefers the upstream spelling. */
export const ArrowUp = PhArrowUp;
export const Info = PhInfo;
export const MagnifyingGlass = PhMagnifyingGlass;
export const PaperPlaneTilt = PhPaperPlaneTilt;
export const Sparkle = PhSparkle;
export const SpinnerGap = PhSpinnerGap;
export const Star = PhStar;
export const Moon = PhMoon;
export const Sun = PhSun;
export const Paperclip = PhPaperclip;
export const Microphone = PhMicrophone;
export const ChatCircle = PhChatCircle;
export const Folder = PhFolder;
export const Lightning = PhLightning;
export const Waveform = PhWaveform;
export const Trash = PhTrash;
export const UserCircle = PhUserCircle;
export const Plugs = PhPlugs;
export const Notebook = PhNotebook;
