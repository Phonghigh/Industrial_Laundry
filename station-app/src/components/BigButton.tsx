interface BigButtonProps {
  label: string;
  subtext: string;
  icon: string;
  onClick: () => void;
  disabled?: boolean;
  variant: "start" | "complete" | "issue";
}

export function BigButton({ label, subtext, icon, onClick, disabled = false, variant }: BigButtonProps) {
  return (
    <button
      className={`huge-btn btn-${variant}`}
      onClick={onClick}
      disabled={disabled}
    >
      {icon} {label}
      <span className="btn-subtext">{subtext}</span>
    </button>
  );
}
