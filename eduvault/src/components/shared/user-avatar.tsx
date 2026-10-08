import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

const SIZE = { sm: "size-7 text-[11px]", md: "size-9 text-xs", lg: "size-14 text-base" } as const;

export function UserAvatar({
  name,
  src,
  size = "md",
  className,
}: {
  name: string;
  src?: string;
  size?: keyof typeof SIZE;
  className?: string;
}) {
  return (
    <Avatar className={cn(SIZE[size], className)}>
      {src && <AvatarImage src={src} alt="" />}
      <AvatarFallback className="bg-primary/10 font-medium text-primary">{initials(name)}</AvatarFallback>
    </Avatar>
  );
}

/** Avatar + name + secondary line, for table cells. */
export function UserCell({ name, email, src }: { name: string; email?: string; src?: string }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <UserAvatar name={name} src={src} size="sm" />
      <div className="min-w-0">
        <p className="truncate font-medium">{name}</p>
        {email && <p className="truncate text-xs text-muted-foreground">{email}</p>}
      </div>
    </div>
  );
}
