"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { notify } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function CopyTransactionButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async (event: React.MouseEvent) => {
    // The button lives inside clickable table rows.
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      notify.success("Transaction ID copied", value);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      notify.error(err, "Couldn't copy to clipboard");
    }
  };

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={copy}
            aria-label={`Copy transaction ID ${value}`}
            className="text-muted-foreground"
          />
        }
      >
        {copied ? <Check className="text-success" /> : <Copy />}
      </TooltipTrigger>
      <TooltipContent>{copied ? "Copied" : "Copy transaction ID"}</TooltipContent>
    </Tooltip>
  );
}
