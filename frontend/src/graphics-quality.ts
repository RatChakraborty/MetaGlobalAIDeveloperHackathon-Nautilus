// Presentation-only quality tiers. These settings change rendering cost and
// visual density only; they never touch recorded samples, timestamps or metrics.
export const QUALITY_TIERS = ['low', 'balanced', 'high', 'cinematic'] as const;
export type QualityTier = typeof QUALITY_TIERS[number];

export type QualitySettings = {
 pixelRatioCap: number;
 shadows: boolean;
 shadowMapSize: number;
 sedimentParticles: number;
 vegetationBlades: number;
 rockCount: number;
 postprocessing: boolean;
};

const SETTINGS: Record<QualityTier, QualitySettings> = {
 low: {pixelRatioCap: 1, shadows: false, shadowMapSize: 0, sedimentParticles: 120, vegetationBlades: 6, rockCount: 24, postprocessing: false},
 balanced: {pixelRatioCap: 1.5, shadows: true, shadowMapSize: 1024, sedimentParticles: 350, vegetationBlades: 12, rockCount: 48, postprocessing: false},
 high: {pixelRatioCap: 2, shadows: true, shadowMapSize: 2048, sedimentParticles: 650, vegetationBlades: 24, rockCount: 72, postprocessing: false},
 cinematic: {pixelRatioCap: 2, shadows: true, shadowMapSize: 2048, sedimentParticles: 650, vegetationBlades: 24, rockCount: 72, postprocessing: true},
};

export function qualityTier(value: string): QualityTier {
 if (!(QUALITY_TIERS as readonly string[]).includes(value)) throw Error('Unknown graphics quality tier');
 return value as QualityTier;
}

export function qualitySettings(tier: QualityTier): Readonly<QualitySettings> {
 return SETTINGS[qualityTier(tier)];
}
