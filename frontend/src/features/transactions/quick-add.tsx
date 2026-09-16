import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "../../components/ui/button";
import { TransactionDialog } from "./transaction-dialog";

export function QuickAdd({ compact = false }: { compact?: boolean }) {
  const [open, setOpen] = useState(false);
  return <><Button className={compact ? "quick-add-fab" : undefined} size={compact ? "icon" : "md"} onClick={() => setOpen(true)}><Plus size={18} aria-hidden="true" /> <span className={compact ? "sr-only" : undefined}>Add transaction</span></Button><TransactionDialog open={open} onOpenChange={setOpen} /></>;
}
