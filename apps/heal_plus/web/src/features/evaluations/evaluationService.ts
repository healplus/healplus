import { supabase } from '../../lib/supabase';
import { clinicalImageUrl, hydrateClinicalImages, persistableImages } from '../../lib/clinicalImages';
import { prepareClinicalImage } from '../../lib/clinicalImagePreparation';
import { uploadClinicalImage } from '../../lib/clinicalImageUpload';
import { getFileExtension } from '../../lib/storagePaths';
import { generateUUID } from '../../lib/uuid';
import type { Evaluation, ImageDraft, WoundImage } from '../../lib/types';
import { validateImageFile } from '../../lib/validators';
import type { EvaluationFormValues } from './evaluationSchema';

export interface EvaluationWriteResult {
  id: string;
  uploadedImageCount: number;
  requestedImageCount: number;
  imageUploadError?: string;
}

export interface EvaluationUploadProgress {
  phase: 'preparing' | 'uploading';
  percent: number;
  completedFiles: number;
  totalFiles: number;
  currentFileName: string;
}

export interface EvaluationWriteOptions {
  signal?: AbortSignal;
  onUploadProgress?: (progress: EvaluationUploadProgress) => void;
}

interface EvaluationAuditOptions {
  previousData?: Record<string, unknown>;
  updatedBy?: string;
}

function validateEvaluationImages(images: ImageDraft[]) {
  for (const image of images) {
    if (!image.file) continue;
    const error = validateImageFile(image.file);
    if (error) throw new Error(error);
  }
}

function friendlyImageUploadError(error: unknown) {
  return typeof error === 'object' && error && 'message' in error ? String((error as any).message) : String(error);
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function existingImageFromDraft(image: ImageDraft): WoundImage | null {
  if (!image.existingDownloadURL || !image.existingStoragePath) return null;

  return {
    id: image.id,
    storagePath: image.existingStoragePath,
    downloadURL: image.existingDownloadURL,
    fileName: image.fileName,
    contentType: image.contentType,
    size: image.size,
    rois: image.existingRois || image.rois,
    uploadedAt: new Date().toISOString()
  };
}

async function mapEvaluationRow(row: any): Promise<Evaluation> {
  const images = await hydrateClinicalImages((row.images || []) as WoundImage[]);

  return {
    id: row.id,
    patientId: row.patient_id,
    patientName: row.patient_name || '',
    date: row.date,
    woundLocation: row.wound_location || '',
    woundEtiology: row.wound_etiology || '',
    painLevel: Number(row.pain_level || 0),
    exudateAmount: row.exudate_amount || '',
    exudateType: row.exudate_type || '',
    borderCharacteristics: row.border_characteristics || '',
    periwoundSkin: row.periwound_skin || '',
    infectionSigns: row.infection_signs || [],
    timers: row.timers || {},
    comorbidities: row.comorbidities || [],
    medications: row.medications || [],
    notes: row.notes || '',
    images,
    signature: row.signature || '',
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };
}

function newlyUploadedPaths(images: ImageDraft[], uploadedImages: WoundImage[]) {
  const newImageIds = new Set(images.filter(image => image.file).map(image => image.id));
  return uploadedImages.filter(image => newImageIds.has(image.id)).map(image => image.storagePath);
}

export function subscribeEvaluations(
  uid: string,
  patientId: string,
  onData: (evaluations: Evaluation[]) => void,
  onError?: (error: Error) => void
) {
  let active = true;
  const fetchEvaluations = async () => {
    const { data, error } = await supabase
      .from('evaluations')
      .select('*')
      .eq('user_id', uid)
      .eq('patient_id', patientId)
      .order('date', { ascending: false });

    if (error) {
      if (active) onError?.(new Error(error.message));
      return;
    }

    const mapped = await Promise.all((data || []).map(mapEvaluationRow));

    if (active) onData(mapped);
  };

  fetchEvaluations();

  const channel = supabase
    .channel('evaluations-changes-' + patientId)
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'evaluations', filter: 'patient_id=eq.' + patientId },
      () => {
        void fetchEvaluations();
      }
    )
    .subscribe();

  return () => {
    active = false;
    void supabase.removeChannel(channel);
  };
}

export async function listEvaluations(uid: string, patientId: string): Promise<Evaluation[]> {
  const { data, error } = await supabase
    .from('evaluations')
    .select('*')
    .eq('user_id', uid)
    .eq('patient_id', patientId)
    .order('date', { ascending: false });

  if (error) throw new Error(error.message);

  return Promise.all((data || []).map(mapEvaluationRow));
}

async function uploadEvaluationImages(
  uid: string,
  patientId: string,
  evaluationId: string,
  images: ImageDraft[],
  options: EvaluationWriteOptions = {}
) {
  const uploaded: WoundImage[] = [];
  const uploadedPaths: string[] = [];
  const pendingImages = images.filter(image => image.file);
  let completedFiles = 0;

  for (const image of images) {
    const existingImage = existingImageFromDraft(image);
    if (!image.file && existingImage) {
      uploaded.push(existingImage);
      continue;
    }

    if (!image.file) continue;
    const error = validateImageFile(image.file);
    if (error) throw new Error(error);

    try {
      options.onUploadProgress?.({
        phase: 'preparing',
        percent: pendingImages.length ? Math.round((completedFiles / pendingImages.length) * 100) : 100,
        completedFiles,
        totalFiles: pendingImages.length,
        currentFileName: image.fileName
      });
      const preparedFile = await prepareClinicalImage(image.file, { signal: options.signal });
      const storagePath = uid + '/' + patientId + '/' + evaluationId + '/' + generateUUID() + '.' + getFileExtension(preparedFile);
      uploadedPaths.push(storagePath);

      await uploadClinicalImage(storagePath, preparedFile, {
        signal: options.signal,
        onProgress: (loadedBytes, totalBytes) => {
          const currentFraction = totalBytes > 0 ? Math.min(1, loadedBytes / totalBytes) : 0;
          options.onUploadProgress?.({
            phase: 'uploading',
            percent: pendingImages.length
              ? Math.round(((completedFiles + currentFraction) / pendingImages.length) * 100)
              : 100,
            completedFiles,
            totalFiles: pendingImages.length,
            currentFileName: image.fileName
          });
        }
      });

      const downloadURL = await clinicalImageUrl(storagePath);

      uploaded.push({
        id: image.id,
        storagePath,
        downloadURL,
        fileName: preparedFile.name,
        contentType: preparedFile.type,
        size: preparedFile.size,
        rois: image.rois,
        uploadedAt: new Date().toISOString()
      });
      completedFiles += 1;
      options.onUploadProgress?.({
        phase: 'uploading',
        percent: Math.round((completedFiles / pendingImages.length) * 100),
        completedFiles,
        totalFiles: pendingImages.length,
        currentFileName: image.fileName
      });
    } catch (uploadError: unknown) {
      if (isAbortError(uploadError)) {
        if (uploadedPaths.length) {
          await supabase.storage.from('wound-images').remove(uploadedPaths);
        }
        throw uploadError;
      }
      const failedPath = uploadedPaths.pop();
      if (failedPath) {
        await supabase.storage.from('wound-images').remove([failedPath]);
      }
      if (existingImage) uploaded.push(existingImage);
      return { uploadedImages: uploaded, imageUploadError: friendlyImageUploadError(uploadError) };
    }
  }

  return { uploadedImages: uploaded };
}

export async function createEvaluation(
  uid: string,
  values: EvaluationFormValues,
  images: ImageDraft[],
  options: EvaluationWriteOptions = {}
): Promise<EvaluationWriteResult> {
  const requestedImageCount = images.filter(image => image.file || image.existingDownloadURL).length;
  const evaluationId = generateUUID();

  validateEvaluationImages(images);
  const { uploadedImages, imageUploadError } = await uploadEvaluationImages(
    uid,
    values.patientId,
    evaluationId,
    images,
    options
  );

  const { error } = await supabase
    .from('evaluations')
    .insert({
      id: evaluationId,
      patient_id: values.patientId,
      user_id: uid,
      patient_name: values.patientName || '',
      date: values.date,
      wound_location: values.woundLocation || '',
      wound_etiology: values.woundEtiology || '',
      pain_level: values.painLevel,
      exudate_amount: values.exudateAmount || '',
      exudate_type: values.exudateType || '',
      border_characteristics: values.borderCharacteristics || '',
      periwound_skin: values.periwoundSkin || '',
      infection_signs: values.infectionSigns || [],
      timers: values.timers || {},
      comorbidities: values.comorbidities || [],
      medications: values.medications || [],
      notes: values.notes || '',
      images: persistableImages(uploadedImages),
      signature: values.signature || ''
    });

  if (error) {
    const paths = newlyUploadedPaths(images, uploadedImages);
    if (paths.length) await supabase.storage.from('wound-images').remove(paths);
    throw new Error(error.message);
  }

  return {
    id: evaluationId,
    uploadedImageCount: uploadedImages.length,
    requestedImageCount,
    imageUploadError
  };
}

export async function updateEvaluation(
  uid: string,
  values: EvaluationFormValues,
  evaluationId: string,
  images: ImageDraft[],
  auditOptions: EvaluationAuditOptions = {},
  options: EvaluationWriteOptions = {}
): Promise<EvaluationWriteResult> {
  const requestedImageCount = images.filter(image => image.file || image.existingDownloadURL).length;

  validateEvaluationImages(images);
  const { uploadedImages, imageUploadError } = await uploadEvaluationImages(
    uid,
    values.patientId,
    evaluationId,
    images,
    options
  );

  const { error } = await supabase
    .from('evaluations')
    .update({
      patient_name: values.patientName || '',
      date: values.date,
      wound_location: values.woundLocation || '',
      wound_etiology: values.woundEtiology || '',
      pain_level: values.painLevel,
      exudate_amount: values.exudateAmount || '',
      exudate_type: values.exudateType || '',
      border_characteristics: values.borderCharacteristics || '',
      periwound_skin: values.periwoundSkin || '',
      infection_signs: values.infectionSigns || [],
      timers: values.timers || {},
      comorbidities: values.comorbidities || [],
      medications: values.medications || [],
      notes: values.notes || '',
      images: persistableImages(uploadedImages),
      signature: values.signature || '',
      updated_at: new Date().toISOString()
    })
    .eq('id', evaluationId)
    .eq('user_id', uid);

  if (error) {
    const paths = newlyUploadedPaths(images, uploadedImages);
    if (paths.length) await supabase.storage.from('wound-images').remove(paths);
    throw new Error(error.message);
  }

  const replacedPaths = images
    .filter(image => image.file && image.existingStoragePath)
    .map(image => image.existingStoragePath as string);
  if (replacedPaths.length) await supabase.storage.from('wound-images').remove(replacedPaths);

  return {
    id: evaluationId,
    uploadedImageCount: uploadedImages.length,
    requestedImageCount,
    imageUploadError
  };
}
