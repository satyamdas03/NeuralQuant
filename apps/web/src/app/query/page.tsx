import { NLQueryBox } from "@/components/NLQueryBox";
import { MessageSquareText } from "lucide-react";

export default function QueryPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 lg:p-6">
      <div className="flex items-center gap-3">
        <MessageSquareText size={20} className="text-primary" />
        <div>
          <h1 className="font-headline text-xl font-bold text-on-surface">Ask the AI</h1>
          <p className="text-xs text-on-surface-variant">
            Natural language queries grounded in NeuralQuant data
          </p>
        </div>
      </div>
      <NLQueryBox />
    </div>
  );
}