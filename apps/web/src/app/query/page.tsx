import { NLQueryBox } from "@/components/NLQueryBox";

export default function QueryPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Ask the AI</h1>
        <p className="text-gray-400 mt-1">
          Natural language queries grounded in NeuralQuant data — the FactSet Mercury experience at retail price.
        </p>
      </div>
      <NLQueryBox />
    </div>
  );
}
