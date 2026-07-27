import { analyzeWithHealAnalyzer, type HealAnalyzerResult } from '../ai/heal-analyzer-service';
import { prepareImageForClinicalAnalysis, type PreparedAnalyzerImage } from './imageQualityService';
import { roisToAnalyzerSelections } from './roiProcessingService';
import type { Roi } from '../../lib/types';

export interface AiInferenceResult {
  status: 'completed' | 'unavailable' | 'skipped';
  analyzerResult?: HealAnalyzerResult;
  preparedImage?: PreparedAnalyzerImage;
  error?: string;
}

export async function runAssistiveAiInference(options: {
  image: File | string | null;
  patientId?: string;
  rois: Roi[];
}): Promise<AiInferenceResult> {
  if (!options.image) {
    return { status: 'skipped', error: 'Imagem nao informada.' };
  }

  let preparedImage: PreparedAnalyzerImage | undefined;
  try {
    preparedImage = await prepareImageForClinicalAnalysis(options.image);
    const analyzerResult = await analyzeWithHealAnalyzer(preparedImage.file, {
      patientId: options.patientId,
      roiSelections: roisToAnalyzerSelections(options.rois)
    });

    return {
      status: 'completed',
      analyzerResult,
      preparedImage
    };
  } catch {
    return {
      status: 'unavailable',
      preparedImage,
      error: 'Inferência da IA indisponível. Preserve o registro e tente novamente mais tarde.'
    };
  }
}
