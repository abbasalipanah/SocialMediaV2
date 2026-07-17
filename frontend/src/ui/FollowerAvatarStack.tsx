const FOLLOWER_AVATARS = [
  "/branding/follower-avatar-5.jpg",
  "/branding/follower-avatar-12.jpg",
  "/branding/follower-avatar-9.jpg",
];

export function FollowerAvatarStack({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden="true" className={`follower-avatar-stack${className ? ` ${className}` : ""}`}>
      {FOLLOWER_AVATARS.map((src) => <img alt="" key={src} src={src} />)}
      <span>+2k</span>
    </div>
  );
}
