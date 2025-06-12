######################################################################
# Copyright 2016, 2023 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
######################################################################
"""
Product API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
  codecov --token=$CODECOV_TOKEN

  While debugging just these tests it's convenient to use this:
    nosetests --stop tests/test_service.py:TestProductRoutes
"""
import os
import logging
from decimal import Decimal
from unittest import TestCase
from service import app
from service.common import status
from service.models import db, init_db, Product
from tests.factories import ProductFactory
from service.models import Category

# Disable all but critical errors during normal test run
# uncomment for debugging failing tests
# logging.disable(logging.CRITICAL)

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)
BASE_URL = "/products"


######################################################################
#  T E S T   C A S E S
######################################################################
# pylint: disable=too-many-public-methods
class TestProductRoutes(TestCase):
    """Product Service tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Product).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        db.session.remove()

    ############################################################
    # Utility function to bulk create products
    ############################################################
    def _create_products(self, count: int = 1) -> list:
        """Factory method to create products in bulk"""
        products = []
        for _ in range(count):
            test_product = ProductFactory()
            response = self.client.post(BASE_URL, json=test_product.serialize())
            self.assertEqual(
                response.status_code, status.HTTP_201_CREATED, "Could not create test product"
            )
            new_product = response.get_json()
            test_product.id = new_product["id"]
            products.append(test_product)
        return products

    ############################################################
    #  T E S T   C A S E S
    ############################################################
    def test_index(self):
        """It should return the index page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b"Product Catalog Administration", response.data)

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data['message'], 'OK')

    # ----------------------------------------------------------
    # TEST CREATE
    # ----------------------------------------------------------
    def test_create_product(self):
        """It should Create a new Product"""
        test_product = ProductFactory()
        logging.debug("Test Product: %s", test_product.serialize())
        response = self.client.post(BASE_URL, json=test_product.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_product = response.get_json()
        self.assertEqual(new_product["name"], test_product.name)
        self.assertEqual(new_product["description"], test_product.description)
        self.assertEqual(Decimal(new_product["price"]), test_product.price)
        self.assertEqual(new_product["available"], test_product.available)
        self.assertEqual(new_product["category"], test_product.category.name)

    def test_create_product_with_no_name(self):
        """It should not Create a Product without a name"""
        product = self._create_products()[0]
        new_product = product.serialize()
        del new_product["name"]
        logging.debug("Product no name: %s", new_product)
        response = self.client.post(BASE_URL, json=new_product)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_product_no_content_type(self):
        """It should not Create a Product with no Content-Type"""
        response = self.client.post(BASE_URL, data="bad data")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_product_wrong_content_type(self):
        """It should not Create a Product with wrong Content-Type"""
        response = self.client.post(BASE_URL, data={}, content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ----------------------------------------------------------
    # TEST GET ALL PRODUCTS
    # ----------------------------------------------------------
    def test_get_all_products(self):
        """It should return all products"""
        self._create_products(count=3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)

    # ----------------------------------------------------------
    # TEST GET PRODUCT BY ID
    # ----------------------------------------------------------
    def test_get_product(self):
        """It should get a product by id"""
        product = self._create_products()[0]
        response = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["id"], product.id)

    def test_get_product_not_found(self):
        """It should return 404 if product not found"""
        response = self.client.get(f"{BASE_URL}/999999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ----------------------------------------------------------
    # TEST UPDATE PRODUCT
    # ----------------------------------------------------------
    def test_update_product(self):
        """It should update an existing product"""
        product = self._create_products()[0]
        update_data = {
            "name": "Updated Name",
            "description": product.description,
            "price": float(product.price),
            "available": product.available,
            "category": product.category.name,
        }
        response = self.client.put(f"{BASE_URL}/{product.id}", json=update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["name"], "Updated Name")

    def test_update_product_not_found(self):
        """It should return 404 when updating non-existing product"""
        update_data = {"name": "DoesNotExist"}
        response = self.client.put(f"{BASE_URL}/999999", json=update_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_product_with_no_name(self):
        """It should not update a Product without a name"""
        product = self._create_products()[0]
        update_data = {"name": ""}
        response = self.client.put(f"{BASE_URL}/{product.id}", json=update_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_product_wrong_content_type(self):
        """It should not update a Product with wrong Content-Type"""
        product = self._create_products()[0]
        response = self.client.put(f"{BASE_URL}/{product.id}", data="bad data", content_type="plain/text")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ----------------------------------------------------------
    # TEST DELETE PRODUCT
    # ----------------------------------------------------------
    def test_delete_product(self):
        """It should delete a product"""
        product = self._create_products()[0]
        response = self.client.delete(f"{BASE_URL}/{product.id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Confirm product is deleted
        get_resp = self.client.get(f"{BASE_URL}/{product.id}")
        self.assertEqual(get_resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_product_not_found(self):
        """It should return 404 when deleting a non-existing product"""
        response = self.client.delete(f"{BASE_URL}/999999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ----------------------------------------------------------
    # TEST LIST PRODUCTS BY NAME
    # ----------------------------------------------------------
    def test_list_products_by_name(self):
        """It should return products filtered by name"""
        # Create some products
        product1 = ProductFactory(name="UniqueName")
        product2 = ProductFactory(name="AnotherName")
        self.client.post(BASE_URL, json=product1.serialize())
        self.client.post(BASE_URL, json=product2.serialize())

        # Query by name
        response = self.client.get(f"{BASE_URL}?name=UniqueName")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "UniqueName")

    # ----------------------------------------------------------
    # TEST LIST PRODUCTS BY CATEGORY
    # ----------------------------------------------------------
    def test_list_products_by_category(self):
        """It should return products filtered by category"""
        # Create products with different categories
        product1 = ProductFactory(category=Category.CLOTHS)
        product2 = ProductFactory(category=Category.TOOLS)
        self.client.post(BASE_URL, json=product1.serialize())
        self.client.post(BASE_URL, json=product2.serialize())

        # Query by category
        response = self.client.get(f"{BASE_URL}?category=CLOTHS")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertTrue(all(p["category"] == "CLOTHS" for p in data))

    # ----------------------------------------------------------
    # TEST LIST PRODUCTS BY AVAILABILITY
    # ----------------------------------------------------------
    def test_list_products_by_availability(self):
        """It should return products filtered by availability"""
        # Create products with different availability
        product1 = ProductFactory(available=True)
        product2 = ProductFactory(available=False)
        self.client.post(BASE_URL, json=product1.serialize())
        self.client.post(BASE_URL, json=product2.serialize())

        # Query by availability
        response = self.client.get(f"{BASE_URL}?available=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertTrue(all(p["available"] is True for p in data))

    ############################################################
    # Additional utility functions
    ############################################################
    def get_product_count(self):
        """save the current number of products"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        return len(data)
