# Copyright 2022 The Nerfstudio Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This file contains NeRF metrics with masking capabilities.
"""

from abc import abstractmethod
from typing import Optional

import torch
from torch import Tensor, nn
from torchmetrics.functional import (
    peak_signal_noise_ratio,
    structural_similarity_index_measure,
)
from torchtyping import TensorType

from nerfstudio.utils.lpips_utils import (
    LearnedPerceptualImagePatchSimilarityWithMasking,
)


class ImageMetricModule(nn.Module):
    """Computes image metrics with masking capabilities.
    We assume that the pred and target inputs are in the range [0, 1].
    """

    def __init__(self):
        super().__init__()
        self.populate_modules()

    def populate_modules(self):
        """Populates the modules that will be used to compute the metric."""

    @abstractmethod
    def forward(
        self,
        preds: TensorType["bs", 3, "H", "W"],
        target: TensorType["bs", 3, "H", "W"],
        mask: Optional[TensorType["bs", 1, "H", "W"]] = None,
    ) -> Tensor:
        """Computes the metric.

        Args:
            preds: Predictions.
            target: Ground truth.
            mask: Mask to use to only compute the metrics where the mask is True.

        Returns:
            TensorType["bs"]: Metric value.
        """


class PSNRModule(ImageMetricModule):
    """Computes PSNR with masking capabilities."""

    def forward(
        self,
        preds: TensorType["bs", 3, "H", "W"],
        target: TensorType["bs", 3, "H", "W"],
        mask: Optional[TensorType["bs", 1, "H", "W"]] = None,
    ) -> Tensor:

        bs, h, w = preds.shape[0], preds.shape[2], preds.shape[3]
        hw = h * w

        psnr_image = peak_signal_noise_ratio(preds=preds, target=target, reduction="none", data_range=1.0, dim=1)
        assert psnr_image.shape == (bs, h, w)

        # the non-masked version
        if mask is None:
            psnr = psnr_image.view(bs, hw).mean(1)
            return psnr

        # the masked version
        psnr_reshaped = psnr_image.view(bs, hw)
        mask_reshaped = mask.view(bs, hw)
        psnr = (psnr_reshaped * mask_reshaped).sum(-1) / hw
        return psnr


class SSIMModule(ImageMetricModule):
    """Computes PSNR with masking capabilities."""

    def forward(
        self,
        preds: TensorType["bs", 3, "H", "W"],
        target: TensorType["bs", 3, "H", "W"],
        mask: Optional[TensorType["bs", 1, "H", "W"]] = None,
    ) -> Tensor:

        bs, h, w = preds.shape[0], preds.shape[2], preds.shape[3]
        hw = h * w

        _, ssim_image = structural_similarity_index_measure(
            preds=preds, target=target, reduction="none", data_range=1.0, return_full_image=True
        )
        ssim_image = ssim_image.mean(1)  # average over the channels
        assert ssim_image.shape == (bs, h, w)

        # the non-masked version
        if mask is None:
            ssim = ssim_image.view(bs, hw).mean(1)
            return ssim

        # the masked version
        ssim_reshaped = ssim_image.view(bs, hw)
        mask_reshaped = mask.view(bs, hw)
        ssim = (ssim_reshaped * mask_reshaped).sum(-1) / hw
        return ssim


class LPIPSModule(ImageMetricModule):
    """Computes LPIPS with masking capabilities."""

    def populate_modules(self):
        # by setting normalize=True, we assume that the pred and target inputs are in the range [0, 1]
        self.lpips_with_masking = LearnedPerceptualImagePatchSimilarityWithMasking(normalize=True)

    def forward(
        self,
        preds: TensorType["bs", 3, "H", "W"],
        target: TensorType["bs", 3, "H", "W"],
        mask: Optional[TensorType["bs", 1, "H", "W"]] = None,
    ) -> Tensor:

        bs, h, w = preds.shape[0], preds.shape[2], preds.shape[3]
        hw = h * w

        with torch.no_grad():
            lpips_image = self.lpips_with_masking(preds, target)
        lpips_image = lpips_image.mean(1)  # average over the channels
        assert lpips_image.shape == (bs, h, w)

        # the non-masked version
        if mask is None:
            lpips = lpips_image.view(bs, hw).mean(1)
            return lpips

        # the masked version
        lpips_reshaped = lpips_image.view(bs, hw)
        mask_reshaped = mask.view(bs, hw)
        lpips = (lpips_reshaped * mask_reshaped).sum(-1) / hw
        return lpips