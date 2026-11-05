"""Hand-only spatial mass over A-owned virtual grid polygons. No contact inference.

No virtual grid generator, no new hand inference, no audio score/fusion implementation.
"""
import copy
import json
from pathlib import Path
import cv2
import numpy as np
from fingertip_probability import CHI2_95,circle_distribution

IDENTITY=['source_id','frame_index','frame_pixel_sha256']


def adapt_grid(grid,observation):
    if observation.get('coordinate_system','original_pixels')!='original_pixels':raise ValueError('Hand center must be original pixels')
    for key in IDENTITY:
        if grid.get(key)!=observation.get(key):raise ValueError('Grid/hand identity mismatch: '+key)
    if abs(grid['frame_pts_s']-observation['frame_pts_s'])>1e-6:raise ValueError('Grid/hand PTS mismatch')
    for key in ['grid_id','grid_version','geometry_source','anchor_status','spacing_source','numbering_status','assumptions']:
        if key not in grid:raise ValueError('Missing grid contract field: '+key)
    if grid.get('is_virtual') is not True:raise ValueError('Expected explicitly virtual grid')
    matrix=np.asarray(grid['M'],float);inverse=np.asarray(grid['M_inv'],float)
    if matrix.shape!=(3,3) or inverse.shape!=(3,3) or not np.isfinite(matrix).all() or not np.isfinite(inverse).all():
        raise ValueError('Invalid grid transforms')
    product=matrix@inverse
    if abs(product[2,2])<1e-12 or not np.allclose(product/product[2,2],np.eye(3),atol=1e-6):raise ValueError('Grid transforms disagree')
    width,height=grid['canvas_size'];polygons=[];ids=set()
    for cell in grid['cells']:
        polygon=np.asarray(cell['polygon'],float)
        if cell.get('estimated')is not True or cell.get('is_virtual')is not True:raise ValueError('Unmarked virtual cell')
        if cell['cell_id']in ids:raise ValueError('Duplicate cell ID')
        ids.add(cell['cell_id'])
        if (polygon.ndim!=2 or polygon.shape[1]!=2 or len(polygon)<3 or not np.isfinite(polygon).all()
            or not cv2.isContourConvex(polygon.astype(np.float32)) or abs(cv2.contourArea(polygon.astype(np.float32)))<1e-8):
            raise ValueError('Invalid convex cell polygon')
        if np.any(polygon<-.001)or np.any(polygon>np.array([width,height])+.001):raise ValueError('Cell outside canvas')
        for prior in polygons:
            area,_=cv2.intersectConvexConvex(polygon.astype(np.float32),prior.astype(np.float32))
            if area>1e-2:raise ValueError('Overlapping virtual cells')
        polygons.append(polygon)
    return grid


def points_in_polygon(points,polygon):
    """Convex halfplanes, either winding. Boundary samples allocated once by caller."""
    polygon=np.asarray(polygon,float)
    a=polygon;b=np.roll(polygon,-1,axis=0)
    delta=b-a
    cross=delta[None,:,0]*(points[:,None,1]-a[None,:,1])-delta[None,:,1]*(points[:,None,0]-a[None,:,0])
    return (cross>=-1e-9).all(axis=1)|(cross<=1e-9).all(axis=1)


def sample_projected(grid,center,radius,samples=16384,seed=20261103):
    if not np.isfinite(radius)or radius<=0:raise ValueError('Positive finite radius required')
    center=np.asarray(center,float)
    if center.shape!=(2,)or not np.isfinite(center).all():raise ValueError('Invalid original center')
    original=np.random.default_rng(seed).standard_normal((samples,2))*(radius/np.sqrt(CHI2_95))+center
    matrix=np.asarray(grid['M'],float)
    homogeneous=np.c_[original,np.ones(samples)]@matrix.T
    valid=np.isfinite(homogeneous).all(axis=1)&(abs(homogeneous[:,2])>1e-9)
    projected=np.full((samples,2),np.nan)
    projected[valid]=homogeneous[valid,:2]/homogeneous[valid,2:]
    return projected,valid


def integrate_points(grid,points,valid):
    width,height=grid['canvas_size'];size=len(points)
    inside=valid&(points[:,0]>=0)&(points[:,0]<width)&(points[:,1]>=0)&(points[:,1]<height)
    assigned=np.zeros(size,bool);values=[]
    for cell in grid['cells']:
        hit=inside&points_in_polygon(points,cell['polygon'])&~assigned
        assigned|=hit
        mass=float(hit.mean())
        values.append(dict(cell_id=cell['cell_id'],virtual_string_num=cell['virtual_string_num'],
            physical_fret_candidate=cell['physical_fret_candidate'],position_mass=mass,
            monte_carlo_se=float(np.sqrt(mass*(1-mass)/size)),
            is_virtual=True,estimated=True,contact='unknown',sounding='unknown',confidence_calibrated=False,
            numbering_status=cell.get('numbering_status',grid['numbering_status'])))
    values.sort(key=lambda c:(-c['position_mass'],c['cell_id']))
    positive=[cell for cell in values if cell['position_mass']>0]
    outside=float((valid&~inside).mean());invalid=float((~valid).mean());unresolved=float((inside&~assigned).mean())
    return dict(cells=values,top1=positive[:1],top2=positive[:2],top3=positive[:3],
        top3_total_mass=sum(c['position_mass']for c in positive[:3]),
        other_cells_mass=float(assigned.mean())-sum(c['position_mass']for c in positive[:3]),
        assigned_mass=float(assigned.mean()),outside_board_mass=outside,
        unresolved_geometry_mass=unresolved,invalid_projection_mass=invalid,
        unassigned_mass=float((~assigned).mean()),mass_total=float(assigned.mean())+outside+unresolved+invalid,
        samples=size,normalization='original total mass; never conditioned on board interior')


def preserve_decision(grid,evidence):
    reasons=[];grade=evidence.get('evidence_grade','unclassified_observation')
    if grade.startswith('abstain'):reasons.append(grade)
    if grade=='multi_crop_supported_unconfirmed_candidate':reasons.append('roi_only_unconfirmed')
    if grade not in ['full_and_multi_crop_supported_candidate','multi_crop_supported_unconfirmed_candidate']and not grade.startswith('abstain'):
        reasons.append('observation_support_unverified')
    if grid.get('geometry_status')!='valid' or not grid.get('precise_geometry_verified',False):reasons.append('geometry_unverified')
    if not grid.get('contact_fret_decision_allowed',False):reasons.append('exact_fret_contact_not_allowed')
    return dict(decision='abstain' if reasons else 'spatial_candidate_only',reasons=reasons,
                upstream_evidence_grade=grade,contact='unknown',sounding='unknown',confirmed_cell=None)


def cell_distribution(grid,observation,radius=6.,samples=16384):
    adapt_grid(grid,observation)
    points,valid=sample_projected(grid,observation['pixel'],radius,samples)
    mass=integrate_points(grid,points,valid)
    return dict(schema_version='hand_cell_distribution.v1',
        **{k:grid[k] for k in ['source_id','frame_index','frame_pts_s','frame_pixel_sha256','grid_id','grid_version','canvas_size','M','M_inv',
                              'geometry_source','anchor_status','spacing_source','numbering_status','assumptions']},
        geometry_status=grid.get('geometry_status','unknown'),
        contact_fret_decision_allowed=grid.get('contact_fret_decision_allowed',False),
        observation=copy.deepcopy(observation),radius_95_original_px=radius,
        radius_calibrated=False,spatial_model='isotropic_original_gaussian_projected_by_homography',
        integration_seed=20261103,integration_method='Monte Carlo in original pixels then project; not a flat Gaussian approximation',
        score_type='conditional_spatial_mass_not_contact_probability',
        geometric_ellipse=circle_distribution(observation['pixel'],radius,np.array(grid['M'])),
        grid_assumptions={k:grid[k] for k in ['geometry_source','anchor_status','spacing_source','numbering_status','assumptions']},
        grid_uncertainty_propagated=False,grid_uncertainty_method='separate_scenario_sensitivity_no_mixture',
        synthetic=bool(grid.get('synthetic',False)),is_virtual=True,
        confidence_calibrated=False,**mass,**preserve_decision(grid,observation.get('evidence',{})))


def segment_distribution(grid,identity,endpoints,radius=6.,samples=16384):
    adapt_grid(grid,identity)
    # A separate uniform-along-segment + Gaussian tube MODEL, not summed tip events.
    rng=np.random.default_rng(20261103);t=rng.random((samples,1))
    original=(1-t)*np.asarray(endpoints[0])+t*np.asarray(endpoints[1])
    original+=rng.standard_normal((samples,2))*(radius/np.sqrt(CHI2_95))
    matrix=np.asarray(grid['M']);hom=np.c_[original,np.ones(samples)]@matrix.T
    valid=np.isfinite(hom).all(axis=1)&(abs(hom[:,2])>1e-9)
    points=np.full((samples,2),np.nan);points[valid]=hom[valid,:2]/hom[valid,2:]
    return dict(model='uniform_segment_with_isotropic_gaussian_tube',pixel_endpoints=endpoints,
        grid_id=grid['grid_id'],grid_version=grid['grid_version'],integration_seed=20261103,
        radius_95_original_px=radius,interpretation='barre_segment_location_hypothesis_not_pressed_strings',
        endpoints_are_observed_joint_locations=True,grid_uncertainty_propagated=False,
        **integrate_points(grid,points,valid),
        **preserve_decision(grid,identity.get('evidence',{})))
