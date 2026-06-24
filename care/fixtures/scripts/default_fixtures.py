from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from care.emr.resources.encounter.constants import StatusChoices
from care.emr.resources.location.spec import (
    FacilityLocationFormChoices,
    FacilityLocationModeChoices,
)
from care.emr.resources.organization.spec import OrganizationTypeChoices
from care.fixtures.constants import (
    DEFAULT_AVAILABILITY,
    FACILITY_DEPARTMENTS,
    INVENTORY_ITEMS,
    LAB_TESTS,
    MANAGING_ORG_USERS,
    HealthcareServiceInternalType,
)
from care.fixtures.context import care_fixture_context


def log(message):
    print(message)  # noqa: T201


def load_fixtures(base):  # noqa: PLR0915, PLR0912
    password = "Ohcn@123"

    geo_organization = base.create_organization(
        org_type=OrganizationTypeChoices.govt.value, name="Kerala"
    )
    base.create_organization(
        org_type=OrganizationTypeChoices.govt.value,
        parent=geo_organization.id,
        name="Ernakulam",
    )
    suppliers = []
    for _ in range(3):
        suppliers.append(
            base.create_organization(
                org_type=OrganizationTypeChoices.product_supplier.value,
                name=f"Supplier {base.fake.company()}",
            )
        )
    role_org_names = [
        "Volunteer",
        "Doctor",
        "Staff",
        "Nurse",
        "Administrator",
        "Facility Admin",
    ]
    role_orgs = {}
    for name in role_org_names:
        role_orgs[name] = base.create_organization(
            org_type=OrganizationTypeChoices.role.value, name=name
        )
    log("Loading organizations completed")

    facility = base.create_facility(
        geo_organization.id,
        name="FACILITY WITH PATIENTS",
        facility_type="Private Hospital",
    )
    facility_id = facility.id
    log("Loading facility completed")

    existing = base.get_facility_organizations(facility_id)
    departments = {}
    admin_org = next((o for o in existing if o.name == "Administration"), None)
    if admin_org:
        departments["Administration"] = admin_org
    for name in FACILITY_DEPARTMENTS:
        departments[name] = base.create_facility_organization(facility_id, name=name)
    general_medicine = departments["General Medicine"]
    log("Loading departments completed")

    ward = base.create_location(
        facility_id,
        name="Ward A",
        form=FacilityLocationFormChoices.wa.value,
        mode=FacilityLocationModeChoices.kind.value,
        organizations=[general_medicine.id],
    )
    for idx in range(1, 6):
        base.create_location(
            facility_id,
            name=f"Bed {idx}",
            description=f"Bed {idx} in {ward.name}",
            parent=ward.id,
            form=FacilityLocationFormChoices.bd.value,
            mode=FacilityLocationModeChoices.instance.value,
            organizations=[general_medicine.id],
        )
    log("Loading locations completed")

    for i in range(1, 6):
        base.create_device(facility_id, registered_name=f"Device {i}")
    log("Loading devices completed")

    roles = base.get_roles()
    default_users = [
        ("Doctor", "care-doctor"),
        ("Staff", "care-staff"),
        ("Nurse", "care-nurse"),
        ("Administrator", "care-admin"),
        ("Volunteer", "care-volunteer"),
        ("Facility Admin", "care-fac-admin"),
    ]
    created_users = {}
    for role_name, username in default_users:
        if role_name not in roles or role_name not in role_orgs:
            continue
        user = base.create_user(
            geo_organization.id,
            role_orgs=[
                {
                    "organization": role_orgs[role_name].id,
                    "role": roles[role_name].id,
                }
            ],
            username=username,
            email=f"{username}@care.test",
            password=password,
        )
        created_users[role_name] = user
    log("Loading users completed")

    patients = []
    for _ in range(10):
        patients.append(base.create_patient(geo_organization.id))
    log("Loading patients completed")

    patient_encounters = []
    for patient in patients:
        encounter = base.create_encounter(
            patient.id,
            facility_id,
            organizations=[general_medicine.id],
            status=StatusChoices.in_progress.value,
        )
        patient_encounters.append((patient, encounter))
    log("Loading encounters completed")

    admin_org = departments.get("Administration")
    if admin_org:
        for role_name in ("Facility Admin", "Nurse", "Staff"):
            user = created_users.get(role_name)
            role = roles.get(role_name)
            if user and role:
                base.add_user_to_facility_organization(
                    facility_id, admin_org.id, user.id, role.id
                )
    log("Loading facility organization memberships completed")

    base.create_facility(
        geo_organization.id,
        name="SECONDARY FACILITY",
        facility_type="Private Hospital",
        is_public=True,
    )
    log("Loading secondary facility completed")

    base.load_questionnaires_from_file([geo_organization.id])
    log("Loading questionnaires completed")

    base.load_templates_from_file(facility=facility_id)
    log("Loading report templates completed")

    load_lab_definitions(base, facility_id, departments)
    log("Loading lab definitions completed")

    load_inventory(base, facility_id, departments, suppliers, ward)
    log("Loading inventory completed")

    load_scheduling(base, facility_id, created_users, patients, departments, roles)
    log("Loading scheduling completed")

    load_clinical_data(
        base,
        facility_id,
        patient_encounters,
        created_users.get("Doctor"),
        ward,
    )
    log("Loading clinical, lab, billing and token data completed")

    setup_managing_organization(base, role_orgs, geo_organization.id, password)
    log("Loading managing organization completed")

    log("\n" + "=" * 55)
    log(f"  {'Username':<25} {'Password':<15} {'Role'}")
    log("-" * 55)
    log(f"  {'admin':<25} {'admin':<15} {'Superuser'}")
    for role_name, username in default_users:
        log(f"  {username:<25} {password:<15} {role_name}")
    for user_def in MANAGING_ORG_USERS:
        if user_def["action"] == "create":
            log(f"  {user_def['username']:<25} {password:<15} {user_def['role']}")
    log("=" * 55 + "\n")


def load_lab_definitions(base, facility_id, departments):
    laboratory = departments["Laboratory"]
    administration = departments.get("Administration")

    lab_location = base.create_location(
        facility_id,
        name="Bio-Chemistry Lab",
        form=FacilityLocationFormChoices.ro.value,
        mode=FacilityLocationModeChoices.kind.value,
        organizations=[laboratory.id],
    )
    base.add_organization_to_location(facility_id, lab_location.id, laboratory.id)
    if administration:
        base.add_organization_to_location(
            facility_id, lab_location.id, administration.id
        )

    lab_charge_category = base.create_resource_category(
        facility_id, "Lab Tests", "charge_item_definition"
    )
    lab_activity_category = base.create_resource_category(
        facility_id, "Lab Tests", "activity_definition"
    )

    lab_service = base.create_healthcare_service(
        facility_id,
        name="Pathology Lab",
        internal_type=HealthcareServiceInternalType.lab.value,
        styling_metadata={"careIcon": "microscope"},
        locations=[lab_location.id],
    )

    for test in LAB_TESTS:
        base.create_lab_test(
            facility_id,
            test,
            service_id=lab_service.id,
            location_id=lab_location.id,
            charge_category_slug=lab_charge_category.slug,
            activity_category_slug=lab_activity_category.slug,
        )


def load_inventory(base, facility_id, departments, suppliers, transfer_destination):
    pharmacy = departments["Pharmacy"]

    pharmacy_location = base.create_location(
        facility_id,
        name="Pharmacy",
        form=FacilityLocationFormChoices.ro.value,
        mode=FacilityLocationModeChoices.kind.value,
        organizations=[pharmacy.id],
    )

    base.create_healthcare_service(
        facility_id,
        name="Main Pharmacy",
        internal_type=HealthcareServiceInternalType.pharmacy.value,
        styling_metadata={},
        locations=[pharmacy_location.id],
    )

    category_names = {item["category"] for item in INVENTORY_ITEMS}
    categories = {}
    for category_name in category_names:
        categories[category_name] = {
            "product_knowledge": base.create_resource_category(
                facility_id, category_name, "product_knowledge"
            ).slug,
            "charge_item_definition": base.create_resource_category(
                facility_id, category_name, "charge_item_definition"
            ).slug,
        }

    supplier_orders = {}
    for idx, supplier in enumerate(suppliers):
        request_order = base.create_request_order(
            facility_id,
            name=f"Initial Stock Request — {supplier.name}",
            destination=pharmacy_location.id,
            supplier=supplier.id,
        )
        delivery_order = base.create_delivery_order(
            facility_id,
            name=f"Initial Stock Delivery — {supplier.name}",
            destination=pharmacy_location.id,
            supplier=supplier.id,
        )
        supplier_orders[idx] = (request_order, delivery_order)

    transfer_seed = None
    for idx, item in enumerate(INVENTORY_ITEMS):
        request_order, delivery_order = supplier_orders[idx % len(suppliers)]

        product, product_knowledge = base.create_facility_product(
            facility_id,
            item,
            categories[item["category"]],
        )

        supply_request = base.create_supply_request(
            order=request_order.id,
            item=product_knowledge.id,
            quantity=item["stock_quantity"],
        )

        delivery = base.create_supply_delivery(
            order=delivery_order.id,
            supplied_item=product.id,
            supplied_item_quantity=item["stock_quantity"],
            supply_request=supply_request.id,
        )

        base.update_supply_delivery(
            delivery.id, status="completed", order=delivery_order.id
        )

        if transfer_seed is None:
            transfer_seed = (product, item["stock_quantity"])

    if transfer_seed and transfer_destination:
        product, stock_quantity = transfer_seed
        transfer_quantity = max(1, stock_quantity // 4)

        pharmacy_inventory_items = base.list_inventory_items(
            facility_id, pharmacy_location.id
        )
        pharmacy_item = next(
            (
                ii
                for ii in pharmacy_inventory_items
                if ii["product"]["id"] == product.id
            ),
            None,
        )
        if pharmacy_item:
            transfer_request_order = base.create_request_order(
                facility_id,
                name="Ward Top-up Request",
                origin=pharmacy_location.id,
                destination=transfer_destination.id,
            )
            transfer_delivery_order = base.create_delivery_order(
                facility_id,
                name="Ward Top-up Delivery",
                origin=pharmacy_location.id,
                destination=transfer_destination.id,
            )
            transfer_supply_request = base.create_supply_request(
                order=transfer_request_order.id,
                item=product.product_knowledge["id"],
                quantity=transfer_quantity,
            )
            transfer_delivery = base.create_supply_delivery(
                order=transfer_delivery_order.id,
                supplied_inventory_item=pharmacy_item["id"],
                supplied_item_quantity=transfer_quantity,
                supply_request=transfer_supply_request.id,
            )
            base.update_supply_delivery(
                transfer_delivery.id,
                status="completed",
                order=transfer_delivery_order.id,
            )


def setup_managing_organization(base, role_orgs, geo_id, password):
    """Create a managing organization, link it to all role orgs, and assign users."""
    role_org_roles = base.get_role_org_roles()

    managing_org = base.create_organization(
        org_type=OrganizationTypeChoices.role.value, name="Health Department"
    )
    managing_org_id = managing_org.id

    for _name, org in role_orgs.items():
        base.link_managing_org(org.id, managing_org_id)

    for user_def in MANAGING_ORG_USERS:
        role_id = role_org_roles[user_def["role"]].id

        if user_def["action"] == "create":
            user = base.create_user(
                geo_id,
                username=user_def["username"],
                email=f"{user_def['username']}@care.test",
                password=password,
            )
            base.assign_org_role(managing_org_id, user.id, role_id)

        elif user_def["action"] == "assign":
            user_data = base.get_user(user_def["username"])
            base.assign_org_role(managing_org_id, user_data.id, role_id)


def load_scheduling(base, facility_id, created_users, patients, departments, roles):
    """Create schedules, token slots, queues, and sample appointments."""
    now = timezone.now()
    valid_from = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    valid_to = (now + timedelta(days=8)).strftime("%Y-%m-%dT23:59:59")

    doctor = created_users.get("Doctor")
    if not doctor:
        return

    admin_org = departments.get("Administration")
    doctor_role = roles.get("Doctor")
    if admin_org and doctor_role:
        base.add_user_to_facility_organization(
            facility_id, admin_org.id, doctor.id, doctor_role.id
        )

    base.create_schedule(
        facility_id,
        resource_type="practitioner",
        resource_id=doctor.id,
        name="Doctor Consultation Schedule",
        valid_from=valid_from,
        valid_to=valid_to,
        availabilities=[DEFAULT_AVAILABILITY],
    )

    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    base.create_token_queue(
        facility_id,
        resource_type="practitioner",
        resource_id=doctor.id,
        date=tomorrow,
    )
    base.create_token_sub_queue(
        facility_id,
        resource_type="practitioner",
        resource_id=doctor.id,
        name="Consultation Room 1",
    )
    base.create_token_category(
        facility_id,
        resource_type="practitioner",
        name="General Consultation",
        shorthand="GEN",
    )

    slots_response = base.get_slots_for_day(
        facility_id,
        resource_type="practitioner",
        resource_id=doctor.id,
        day=tomorrow,
    )
    slots = slots_response.get("results", [])
    if slots:
        booked_patients = patients[: min(3, len(patients), len(slots))]
        for idx, patient in enumerate(booked_patients):
            base.create_appointment(
                facility_id,
                slot_id=slots[idx].id,
                patient_id=patient.id,
                note=f"Auto-booked fixture appointment {idx + 1}",
            )


def _snomed(code, display):
    return {"system": "http://snomed.info/sct", "code": code, "display": display}


def load_clinical_data(base, facility_id, patient_encounters, doctor, ward):
    """Populate clinical chart, lab, billing and token data for demo patients.

    Each sub-step is wrapped in a savepoint so a single failure (e.g. inventory
    running low) is logged and skipped without aborting the whole fixture load.
    """
    from care.emr.models import InventoryItem, TokenCategory, TokenQueue

    def safe(label, fn):
        try:
            with transaction.atomic():
                return fn()
        except Exception as e:
            log(f"  [skip] {label}: {type(e).__name__}: {str(e)[:160]}")
            return None

    symptoms = [
        _snomed("386661006", "Fever"),
        _snomed("25064002", "Headache"),
        _snomed("422587007", "Nausea"),
        _snomed("267036007", "Dyspnea"),
        _snomed("49727002", "Cough"),
    ]
    diagnoses = [
        _snomed("44054006", "Type 2 Diabetes Mellitus"),
        _snomed("38341003", "Hypertension"),
        _snomed("195967001", "Asthma"),
        _snomed("13645005", "COPD"),
        _snomed("709044004", "Chronic Kidney Disease"),
    ]
    allergies = [
        _snomed("373270004", "Penicillin"),
        _snomed("91935009", "Peanut"),
        _snomed("425525006", "Dairy product"),
        _snomed("293586001", "Aspirin"),
    ]
    medications = [
        _snomed("387207008", "Ibuprofen"),
        _snomed("387517004", "Paracetamol"),
        _snomed("372687004", "Amoxicillin"),
        _snomed("372567009", "Metformin"),
    ]
    lab_tests = [
        _snomed("26604007", "Complete blood count"),
        _snomed("33747003", "Glucose measurement"),
        _snomed("166312007", "Blood chemistry"),
    ]
    lab_category = {
        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
        "code": "LAB",
        "display": "Laboratory",
    }
    doctor_id = doctor.id if doctor else None
    ward_id = ward.id if ward else None

    # --- Clinical chart for every patient -------------------------------
    for idx, (patient, encounter) in enumerate(patient_encounters):
        pid, eid = patient.id, encounter.id
        safe(
            "symptom",
            lambda p=pid, e=eid, i=idx: base.create_symptom(
                p, e, symptoms[i % len(symptoms)]
            ),
        )
        safe(
            "diagnosis",
            lambda p=pid, e=eid, i=idx: base.create_diagnosis(
                p, e, diagnoses[i % len(diagnoses)]
            ),
        )
        safe(
            "allergy",
            lambda p=pid, e=eid, i=idx: base.create_allergy_intolerance(
                p, e, allergies[i % len(allergies)]
            ),
        )
        safe(
            "medication_request",
            lambda p=pid, e=eid, i=idx: base.create_medication_request(
                p, e, medications[i % len(medications)]
            ),
        )
        if doctor_id:
            safe(
                "prescription",
                lambda p=pid, e=eid: base.create_medication_request_prescription(
                    p, e, doctor_id
                ),
            )
        safe("consent", lambda p=pid, e=eid: base.create_consent(p, e))

    # --- Lab orders + results for the first half of patients ------------
    for idx, (patient, encounter) in enumerate(patient_encounters[:5]):
        code = lab_tests[idx % len(lab_tests)]

        def lab_chain(p=patient, e=encounter, c=code):
            sr = base.create_service_request(
                facility_id, e.id, doctor_id, c, [ward_id] if ward_id else []
            )
            base.create_specimen(
                facility_id, sr.id, _snomed("122555007", "Venous blood specimen")
            )
            report = base.create_diagnostic_report(p.id, sr.id, lab_category)
            base.add_observations_to_report(
                p.id,
                report.id,
                [
                    {
                        "observation": {
                            "status": "final",
                            "value_type": "quantity",
                            "main_code": c,
                            "effective_datetime": timezone.now().isoformat(),
                            "value": {
                                "value": "95",
                                "unit": {
                                    "system": "http://unitsofmeasure.org",
                                    "code": "mg/dL",
                                    "display": "mg/dL",
                                },
                            },
                        },
                        "observation_definition": None,
                        "observation_id": None,
                    }
                ],
            )

        safe("lab_chain", lab_chain)

    # --- Medication dispense (auto-creates Account + ChargeItem) --------
    inventory_item = (
        InventoryItem.objects.select_related("location")
        .filter(location__facility__external_id=facility_id, net_content__gte=5)
        .order_by("-net_content")
        .first()
    )
    if inventory_item and inventory_item.location:
        loc_id = str(inventory_item.location.external_id)
        item_id = str(inventory_item.external_id)
        for _patient, encounter in patient_encounters[5:8]:
            safe(
                "medication_dispense",
                lambda e=encounter: base.create_medication_dispense(
                    e.id, loc_id, item_id, quantity=1
                ),
            )

    # --- Explicit billing chain for patients without a dispense ---------
    unit_price_components = [
        {
            "monetary_component_type": "base",
            "currency": "INR",
            "amount": "500.00",
            "code": _snomed("consult-001", "Consultation"),
        }
    ]
    for patient, encounter in patient_encounters[8:10]:

        def billing_chain(p=patient, e=encounter):
            account = base.create_account(facility_id, p.id)
            charge_item = base.create_charge_item(
                facility_id, e.id, account.id, unit_price_components
            )
            invoice = base.create_invoice(facility_id, account.id, [charge_item.id])
            base.create_payment_reconciliation(
                facility_id, account.id, invoice.id, "500.00"
            )

        safe("billing_chain", billing_chain)

    # --- Tokens for the first few patients ------------------------------
    queue = TokenQueue.objects.first()
    category = TokenCategory.objects.first()
    if queue and category:
        q_id = str(queue.external_id)
        c_id = str(category.external_id)
        for patient, _encounter in patient_encounters[:3]:
            safe(
                "token",
                lambda p=patient: base.create_token(facility_id, q_id, p.id, c_id),
            )


if __name__ == "__main__":
    with care_fixture_context() as base:
        load_fixtures(base)
